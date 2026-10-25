import time
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("sentinel.audit")

class AuditLogEntry(BaseModel):
    log_id: str
    timestamp: float = Field(default_factory=time.time)
    intent_id: str
    user_id: str
    raw_prompt: str
    status: str  # "APPROVED", "PAYMENT_PENDING", "PAYPAL_ORDER_CREATE_FAILED",
                  # "BLOCKED", "HOLD", "ESCALATED_APPROVED", "ESCALATED_REJECTED",
                  # "CAPTURE_FAILED", "PAYMENT_COMPLETED"
    reason: Optional[str] = None
    checkout_payload: Dict[str, Any]
    policy_rules: Dict[str, Any]
    paypal_order_id: Optional[str] = None
    payment_state: Optional[str] = None  # "completed", "pending", "failed", "unverified"

# In-memory storage for transaction audit trails
_audit_trail_db: List[AuditLogEntry] = []

def record_audit_log(entry: AuditLogEntry) -> None:
    """Appends an immutable audit record to the store."""
    _audit_trail_db.append(entry)
    logger.info(
        f"[AUDIT LOGGED] ID: {entry.log_id} | User: {entry.user_id} | "
        f"Status: {entry.status} | Order ID: {entry.paypal_order_id or 'N/A'}"
    )

def get_all_audit_logs() -> List[AuditLogEntry]:
    """Retrieves all transaction audit records sorted by timestamp descending."""
    return sorted(_audit_trail_db, key=lambda x: x.timestamp, reverse=True)