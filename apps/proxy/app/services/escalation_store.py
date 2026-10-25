import threading
from typing import Dict, Any, Optional
from pydantic import BaseModel

class EscalationRecord(BaseModel):
    escalation_id: str
    status: str  # "PENDING", "APPROVED", "REJECTED"
    reason: str
    checkout_payload: Dict[str, Any]
    policy: Dict[str, Any]

# In-memory store (Replace with Redis in production environments)
_escalation_db: Dict[str, EscalationRecord] = {}

_lock = threading.Lock()

def save_escalation(record: EscalationRecord) -> None:
    _escalation_db[record.escalation_id] = record

def get_escalation(escalation_id: str) -> Optional[EscalationRecord]:
    return _escalation_db.get(escalation_id)

def update_escalation_status(escalation_id: str, status: str) -> bool:
    with _lock:
        if escalation_id in _escalation_db:
            _escalation_db[escalation_id].status = status
            return True
        return False

def claim_escalation(escalation_id: str) -> bool:
    with _lock:
        rec = _escalation_db.get(escalation_id)
        if not rec or rec.status != "PENDING":
            return False
        rec.status = "PROCESSING"
        return True