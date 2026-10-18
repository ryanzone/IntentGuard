import logging
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger("sentinel.notifier")

class EscalationNotifier:
    def __init__(self, base_url: str = None):
        # Dynamically pulls environment settings or defaults to request host
        self.base_url = base_url or getattr(settings, "GATEWAY_BASE_URL", "http://127.0.0.1:8000")

    def build_notification_payload(
        self, escalation_id: str, reason: str, checkout_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Formats the interactive approval message dynamically from cart contents."""
        line_items = checkout_payload.get("line_items", [])
        total_amount = checkout_payload.get("amount", 0)
        currency = checkout_payload.get("currency", "INR")

        items_summary = "\n".join(
            [f"• {item.get('name', 'Item')} (₹{item.get('price', 0):,})" for item in line_items]
        )

        approve_link = f"{self.base_url}/v1/escalations/{escalation_id}/decision?action=APPROVE"
        reject_link = f"{self.base_url}/v1/escalations/{escalation_id}/decision?action=REJECT"

        message = (
            f"⚠️ *PayPal IntentGuard: Action Required*\n\n"
            f"A transaction was placed on *HOLD* due to ambiguity.\n\n"
            f"*Reason:* {reason}\n\n"
            f"*Cart Summary ({currency} {total_amount:,}):*\n{items_summary}\n\n"
            f"Please review and respond:\n"
            f"✅ Approve: {approve_link}\n"
            f"❌ Reject: {reject_link}"
        )

        return {
            "escalation_id": escalation_id,
            "formatted_message": message,
            "actions": {
                "approve_url": approve_link,
                "reject_url": reject_link
            }
        }

    async def send_whatsapp_escalation(
        self, escalation_id: str, reason: str, checkout_payload: Dict[str, Any]
    ) -> None:
        """Simulates/dispatches WhatsApp outbound notification webhook."""
        payload = self.build_notification_payload(escalation_id, reason, checkout_payload)
        logger.info(
            f"\n--- [OUTBOUND WHATSAPP ESCALATION DISPATCH] ---\n"
            f"{payload['formatted_message']}\n"
            f"------------------------------------------------"
        )

notifier = EscalationNotifier()