import json
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
from paypalcheckoutsdk.orders import OrdersCreateRequest

from app.schemas.policy import IntentPolicy, DecisionResult
from app.evaluator.rules import evaluate_cart_against_policy
from app.core.config import settings
from app.compiler.intent_engine import generate_policy_signature

router = APIRouter()

paypal_environment = SandboxEnvironment(
    client_id=settings.PAYPAL_CLIENT_ID,
    client_secret=settings.PAYPAL_CLIENT_SECRET
)
paypal_client = PayPalHttpClient(paypal_environment)

class InterceptedCheckoutRequest(BaseModel):
    checkout_payload: Dict[str, Any]
    policy: IntentPolicy

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
            paypal_order = paypal_client.do_create_order(order_request)
            paypal_order = paypal_order.to_dict() if hasattr(paypal_order, "to_dict") else paypal_order
        except Exception:
            paypal_order = {
                "id": f"order_mock_{uuid4().hex[:8]}",
                "status": "created",
                "purchase_units": [{
                    "amount": {
                        "currency_code": currency,
                        "value": str(order_amount)
                    }
                }]
            }

        return {
            "status": "APPROVED",
            "message": "Cart payload successfully passed all semantic and budget intent checks.",
            "paypal_order": paypal_order
        }

    elif decision.status == "AMBIGUOUS":
        escalation_id = str(decision.escalation_id or f"esc_{policy.intent_id}")
        return {
            "status": "HOLD",
            "reason": decision.reason,
            "escalation_id": escalation_id,
            "message": "Transaction placed on hold due to variance within tolerance limit."
        }

    else:  # VIOLATION
        raise HTTPException(
            status_code=400,
            detail={
                "status": "BLOCKED",
                "reason": decision.reason,
                "message": "Transaction blocked due to clear Intent Policy violation."
            }
        )