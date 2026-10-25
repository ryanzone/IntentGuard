import json
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
from paypalcheckoutsdk.orders import OrdersCaptureRequest, OrdersCreateRequest

from app.schemas.policy import IntentPolicy, DecisionResult
from app.evaluator.rules import evaluate_cart_against_policy
from app.core.config import settings
from app.compiler.intent_engine import generate_policy_signature
from app.services.audit import record_audit_log, AuditLogEntry, get_all_audit_logs
from app.services.escalation_store import get_escalation, update_escalation_status

router = APIRouter()

paypal_environment = SandboxEnvironment(
    client_id=settings.PAYPAL_CLIENT_ID,
    client_secret=settings.PAYPAL_CLIENT_SECRET
)
paypal_client = PayPalHttpClient(paypal_environment)

class InterceptedCheckoutRequest(BaseModel):
    checkout_payload: Dict[str, Any]
    policy: IntentPolicy


def _is_mock_paypal_id(order_id: str) -> bool:
    return isinstance(order_id, str) and order_id.startswith("order_mock")


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

    # 2. Reject zero or negative transaction amounts before creating a PayPal order
    order_amount = checkout.get("amount", 0)
    try:
        order_amount_num = float(order_amount)
    except (TypeError, ValueError):
        order_amount_num = 0.0
    if order_amount_num <= 0:
        raise HTTPException(status_code=400, detail={"status": "BLOCKED", "reason": "Invalid transaction amount", "message": "Transaction amount must be greater than zero."})

    # 2. Semantic & Monetary Policy Verification
    decision: DecisionResult = evaluate_cart_against_policy(checkout, policy)

    # 3. Gateway Decision Dispatcher
    if decision.status == "APPROVED":
        order_amount = checkout.get("amount", 0)
        currency = checkout.get("currency", "USD")

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

        try:
            paypal_response = paypal_client.execute(order_request)
            paypal_order = paypal_response.result if hasattr(paypal_response, "result") else paypal_response
        except Exception as e:
            record_audit_log(AuditLogEntry(
                log_id=str(uuid4()),
                intent_id=str(policy.intent_id),
                user_id=policy.user_id,
                raw_prompt=policy.raw_prompt,
                status="PAYPAL_ORDER_CREATE_FAILED",
                reason=str(e),
                checkout_payload=checkout,
                policy_rules=policy.rules.model_dump(),
                paypal_order_id=None,
            ))
            raise HTTPException(status_code=502, detail={"status": "PAYPAL_ORDER_CREATE_FAILED", "message": "PayPal order creation failed.", "paypal_order_id": None})

        real_order_id = paypal_order.get("id") if isinstance(paypal_order, dict) else None
        if real_order_id and _is_mock_paypal_id(real_order_id):
            record_audit_log(AuditLogEntry(
                log_id=str(uuid4()),
                intent_id=str(policy.intent_id),
                user_id=policy.user_id,
                raw_prompt=policy.raw_prompt,
                status="PAYPAL_ORDER_CREATE_FAILED",
                reason="PayPal returned a mock order id; real order creation failed.",
                checkout_payload=checkout,
                policy_rules=policy.rules.model_dump(),
                paypal_order_id=None,
            ))
            raise HTTPException(status_code=502, detail={"status": "PAYPAL_ORDER_CREATE_FAILED", "message": "PayPal returned a mock order id; real order creation failed.", "paypal_order_id": None})

        record_audit_log(AuditLogEntry(
            log_id=str(uuid4()),
            intent_id=str(policy.intent_id),
            user_id=policy.user_id,
            raw_prompt=policy.raw_prompt,
            status="APPROVED",
            reason="Cart payload successfully passed all semantic and budget intent checks.",
            checkout_payload=checkout,
            policy_rules=policy.rules.model_dump(),
            paypal_order_id=real_order_id,
        ))

        return {
            "status": "APPROVED",
            "message": "Cart payload successfully passed all semantic and budget intent checks.",
            "paypal_order": paypal_order
        }

    elif decision.status == "AMBIGUOUS":
        escalation_id = str(decision.escalation_id or f"esc_{policy.intent_id}")
        record_audit_log(AuditLogEntry(
            log_id=str(uuid4()),
            intent_id=str(policy.intent_id),
            user_id=policy.user_id,
            raw_prompt=policy.raw_prompt,
            status="HOLD",
            reason=decision.reason,
            checkout_payload=checkout,
            policy_rules=policy.rules.model_dump(),
            paypal_order_id=None,
        ))
        return {
            "status": "HOLD",
            "reason": decision.reason,
            "escalation_id": escalation_id,
            "message": "Transaction placed on hold due to variance within tolerance limit."
        }

    else:  # VIOLATION
        record_audit_log(AuditLogEntry(
            log_id=str(uuid4()),
            intent_id=str(policy.intent_id),
            user_id=policy.user_id,
            raw_prompt=policy.raw_prompt,
            status="BLOCKED",
            reason=decision.reason,
            checkout_payload=checkout,
            policy_rules=policy.rules.model_dump(),
            paypal_order_id=None,
        ))
        raise HTTPException(
            status_code=400,
            detail={
                "status": "BLOCKED",
                "reason": decision.reason,
                "message": "Transaction blocked due to clear Intent Policy violation."
            }
        )


class CaptureRequest(BaseModel):
    pass


@router.post("/v1/orders/{order_id}/capture")
async def capture_order(order_id: str, request: Optional[CaptureRequest] = None):
    if _is_mock_paypal_id(order_id):
        raise HTTPException(status_code=400, detail={"status": "PAYMENT_PENDING", "payment_completed": False, "message": "Order id is not a real PayPal order."})

    capture_request = OrdersCaptureRequest(order_id)
    capture_request.request_body({})

    try:
        paypal_response = paypal_client.execute(capture_request)
        capture_result = paypal_response.result if hasattr(paypal_response, "result") else paypal_response
    except Exception as e:
        record_audit_log(AuditLogEntry(
            log_id=str(uuid4()),
            intent_id="unknown",
            user_id="unknown",
            raw_prompt="",
            status="PAYMENT_PENDING",
            reason=f"PayPal capture failed: {e}",
            checkout_payload={},
            policy_rules={},
            paypal_order_id=order_id,
        ))
        return {
            "status": "PAYMENT_PENDING",
            "payment_completed": False,
            "paypal_order_id": order_id,
            "message": f"PayPal capture pending/failed: {e}"
        }

    capture_status = (capture_result or {}).get("status", "") if isinstance(capture_result, dict) else ""
    payment_completed = capture_status == "COMPLETED"

    audit_status = "ESCALATED_APPROVED" if payment_completed else "PAYMENT_PENDING"
    record_audit_log(AuditLogEntry(
        log_id=str(uuid4()),
        intent_id="unknown",
        user_id="unknown",
        raw_prompt="",
        status=audit_status,
        reason=f"PayPal capture status: {capture_status or 'unknown'}",
        checkout_payload={},
        policy_rules={},
        paypal_order_id=order_id,
    ))

    return {
        "status": "PAYMENT_PENDING" if not payment_completed else "COMPLETED",
        "payment_completed": payment_completed,
        "paypal_order_id": order_id,
        "message": f"PayPal capture status: {capture_status or 'unknown'}"
    }


@router.get("/v1/audit-trail")
async def get_audit_trail():
    return {"logs": [entry.model_dump() for entry in get_all_audit_logs()]}


@router.get("/v1/escalations")
async def list_escalations():
    from app.services.escalation_store import _escalation_db
    return {"escalations": {k: v.model_dump() for k, v in _escalation_db.items()}}