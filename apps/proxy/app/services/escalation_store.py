from typing import Dict, Any, Optional
from pydantic import BaseModel
import threading

class EscalationRecord(BaseModel):
    escalation_id: str
    status: str  # "PENDING", "APPROVED", "REJECTED"
    reason: str
    checkout_payload: Dict[str, Any]
    policy: Dict[str, Any]
    paypal_order_id: Optional[str] = None

# In-memory store (Replace with Redis in production environments)
_escalation_db: Dict[str, EscalationRecord] = {}
_store_lock = threading.Lock()

def save_escalation(record: EscalationRecord) -> None:
    with _store_lock:
        _escalation_db[record.escalation_id] = record

def get_escalation(escalation_id: str) -> Optional[EscalationRecord]:
    with _store_lock:
        return _escalation_db.get(escalation_id)

def update_escalation_status(escalation_id: str, status: str) -> bool:
    with _store_lock:
        if escalation_id in _escalation_db:
            _escalation_db[escalation_id].status = status
            return True
        return False

def update_escalation_order_id(escalation_id: str, order_id: str) -> bool:
    with _store_lock:
        if escalation_id in _escalation_db:
            _escalation_db[escalation_id].paypal_order_id = order_id
            return True
        return False

def claim_escalation(escalation_id: str) -> bool:
    """
    Atomically claim a PENDING escalation for processing.
    Returns True if the caller won the claim (status was PENDING and is now CLAIMED),
    False if another caller already claimed it or the escalation does not exist.
    """
    with _store_lock:
        record = _escalation_db.get(escalation_id)
        if record and record.status == "PENDING":
            record.status = "CLAIMED"
            return True
        return False

def get_escalation_status(escalation_id: str) -> Optional[str]:
    with _store_lock:
        record = _escalation_db.get(escalation_id)
        return record.status if record else None