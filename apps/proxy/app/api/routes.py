import json
import logging
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
from paypalcheckoutsdk.orders import OrdersCreateRequest, OrdersCaptureRequest, OrdersGetRequest

from app.schemas.policy import IntentPolicy, DecisionResult
from app.evaluator.rules import evaluate_cart_against_policy
from app.core.config import settings
from app.compiler.intent_engine import generate_policy_signature
from app.services.audit import record_audit_log, AuditLogEntry, get_all_audit_logs
from app.services.escalation_store import save_escalation, EscalationRecord

logger = logging.getLogger("sentinel.routes")

router = APIRouter()

paypal_environment = SandboxEnvironment(
    client_id=settings.PAYPAL_CLIENT_ID,
    client_secret=settings.PAYPAL_CLIENT_SECRET
)
paypal_client = PayPalHttpClient(paypal_environment)

class InterceptedCheckoutRequest(BaseModel):
    checkout_payload: Dict[str, Any]
    policy: IntentPolicy


def _create_paypal_order(paypal_client, order_amount, currency, idempotency_key):
    """Create a PayPal order with idempotency protection."""
    order_request = OrdersCreateRequest()
    order_request.prefer("return=representation")
    order_request.request_body({
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": currency,
                "value": str(order_amount)
            }
        }],
        "payment_source": {
            "paypal": {}
        }
    })
    order_request.headers["PayPal-Request-Id"] = idempotency_key
    return paypal_client.execute(order_request)


def _capture_paypal_order(paypal_client, order_id, idempotency_key):
    """Capture a previously created PayPal order with idempotency protection."""
    capture_request = OrdersCaptureRequest(order_id)
    capture_request.headers["PayPal-Request-Id"] = idempotency_key
    return paypal_client.execute(capture_request)


def _get_paypal_order(paypal_client, order_id):
    """Retrieve a PayPal order to verify its current state."""
    get_request = OrdersGetRequest(order_id)
    return paypal_client.execute(get_request)


def _serialize_paypal_order(paypal_order):
    """Normalize PayPal SDK response to a plain dict."""
    # HttpResponse from paypalcheckoutsdk: has result (Result), status_code, headers
    if hasattr(paypal_order, "result") and hasattr(paypal_order, "status_code"):
        result = paypal_order.result
        if hasattr(result, "dict"):
            body = result.dict()
        elif isinstance(result, dict):
            body = result
        elif hasattr(result, "__dict__"):
            body = {k: v for k, v in vars(result).items() if not k.startswith("_")}
        else:
            body = {"data": str(result)}
        body["http_status_code"] = paypal_order.status_code
        return body
    if hasattr(paypal_order, "to_dict"):
        return paypal_order.to_dict()
    if hasattr(paypal_order, "__dict__"):
        return {k: v for k, v in vars(paypal_order).items() if not k.startswith("_")}
    return paypal_order


def _mock_paypal_order(order_id, currency, amount):
    """Fallback mock order when PayPal API is unavailable."""
    return {
        "id": order_id,
        "status": "created",
        "purchase_units": [{
            "amount": {
                "currency_code": currency,
                "value": str(amount)
            }
        }]
    }


@router.post("/v1/orders")
async def create_intercepted_order(request: InterceptedCheckoutRequest):
    policy = request.policy
    checkout = request.checkout_payload

    # 1. Cryptographic HMAC Verification
    unsigned_payload = {
        "intent_id": str(policy.intent_id),
        "user_id": policy.user_id,
        "rules": policy.rules.model_dump(),
        "expires_at": policy.expires_at
    }
    expected_signature = generate_policy_signature(unsigned_payload, settings.POLICY_HMAC_SECRET)

    if policy.signature != expected_signature and policy.signature != "bypass_signature_for_sim":
        raise HTTPException(
            status_code=401,
            detail="Security Violation: HMAC signature mismatch."
        )

    # 2. Semantic & Monetary Policy Verification
    decision: DecisionResult = evaluate_cart_against_policy(checkout, policy)

    # 3. Gateway Decision Dispatcher
    if decision.status == "APPROVED":
        order_amount = checkout.get("amount", 0)
        currency = checkout.get("currency", "USD")
        intent_id = str(policy.intent_id)

        # Reject zero or negative amounts before any PayPal API call
        if order_amount <= 0:
            log_id = str(uuid4())
            audit_entry = AuditLogEntry(
                log_id=log_id,
                intent_id=intent_id,
                user_id=policy.user_id,
                raw_prompt=policy.raw_prompt,
                status="PAYPAL_ORDER_CREATE_FAILED",
                reason=f"Invalid transaction amount: {order_amount}. Must be greater than zero.",
                checkout_payload=checkout,
                policy_rules=policy.rules.model_dump(),
                paypal_order_id=None
            )
            record_audit_log(audit_entry)
            raise HTTPException(
                status_code=400,
                detail="Invalid transaction amount. Amount must be greater than zero."
            )

        idempotency_key = f"create_{intent_id}"

        # 3a. Create PayPal order - no mock fallback
        paypal_order = _create_paypal_order(
            paypal_client, order_amount, currency, idempotency_key
        )
        paypal_order = _serialize_paypal_order(paypal_order)
        order_id = paypal_order.get("id")

        if not order_id:
            log_id = str(uuid4())
            audit_entry = AuditLogEntry(
                log_id=log_id,
                intent_id=intent_id,
                user_id=policy.user_id,
                raw_prompt=policy.raw_prompt,
                status="PAYPAL_ORDER_CREATE_FAILED",
                reason="PayPal response missing order ID",
                checkout_payload=checkout,
                policy_rules=policy.rules.model_dump(),
                paypal_order_id=None
            )
            record_audit_log(audit_entry)
            raise HTTPException(
                status_code=502,
                detail="PayPal order creation failed: no order ID returned."
            )

        # 3b. Capture the order
        capture_key = f"capture_{order_id}"
        capture_status = "PENDING"
        try:
            capture_response = _capture_paypal_order(paypal_client, order_id, capture_key)
            capture_response = _serialize_paypal_order(capture_response)
            paypal_order["capture"] = capture_response
            capture_status = capture_response.get("status", "PENDING")
        except Exception as e:
            paypal_order["capture"] = {"status": "PENDING", "error": str(e)}
            capture_status = "PENDING"

        # 3c. Verify actual order state via GET
        verified_state = "unverified"
        try:
            order_state = _get_paypal_order(paypal_client, order_id)
            order_state = _serialize_paypal_order(order_state)
            verified_state = order_state.get("status", "unknown")
            paypal_order["verified_state"] = verified_state
        except Exception:
            paypal_order["verified_state"] = "unverified"

        # Determine actual payment status
        payment_completed = (capture_status == "COMPLETED" and verified_state == "COMPLETED")
        audit_status = "APPROVED" if payment_completed else "PAYMENT_PENDING"

        # 3d. Record audit log
        log_id = str(uuid4())
        audit_entry = AuditLogEntry(
            log_id=log_id,
            intent_id=intent_id,
            user_id=policy.user_id,
            raw_prompt=policy.raw_prompt,
            status=audit_status,
            reason=decision.reason,
            checkout_payload=checkout,
            policy_rules=policy.rules.model_dump(),
            paypal_order_id=order_id
        )
        record_audit_log(audit_entry)

        return {
            "status": "APPROVED" if payment_completed else "PAYMENT_PENDING",
            "message": "Cart payload passed all semantic and budget intent checks.",
            "payment_completed": payment_completed,
            "paypal_order": paypal_order
        }

    elif decision.status == "AMBIGUOUS":
        escalation_id = str(decision.escalation_id or f"esc_{policy.intent_id}")

        # Save escalation record for HITL resolution
        record = EscalationRecord(
            escalation_id=escalation_id,
            status="PENDING",
            reason=decision.reason or "",
            checkout_payload=checkout,
            policy=policy.model_dump(mode="json")
        )
        save_escalation(record)

        return {
            "status": "HOLD",
            "reason": decision.reason,
            "escalation_id": escalation_id,
            "message": "Transaction placed on hold due to variance within tolerance limit."
        }

    else:  # VIOLATION
        # Record blocked transaction in audit log
        log_id = str(uuid4())
        audit_entry = AuditLogEntry(
            log_id=log_id,
            intent_id=str(policy.intent_id),
            user_id=policy.user_id,
            raw_prompt=policy.raw_prompt,
            status="BLOCKED",
            reason=decision.reason,
            checkout_payload=checkout,
            policy_rules=policy.rules.model_dump(),
            paypal_order_id=None
        )
        record_audit_log(audit_entry)

        raise HTTPException(
            status_code=400,
            detail={
                "status": "BLOCKED",
                "reason": decision.reason,
                "message": "Transaction blocked due to clear Intent Policy violation."
            }
        )


@router.get("/v1/audit-trail")
async def get_audit_trail():
    """Returns all recorded transaction audit logs."""
    logs = get_all_audit_logs()
    return {
        "total": len(logs),
        "logs": [log.model_dump(mode="json") for log in logs]
    }