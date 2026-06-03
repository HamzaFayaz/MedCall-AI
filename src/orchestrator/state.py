from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.messages import BaseMessage

from src.orchestrator.call_state import IdentityFields


@dataclass
class OrchestratorSessionState:
    """In-memory orchestrator state for one call (session_id matches CallSession)."""

    session_id: str
    active_node: str = "PATIENT_IDENTIFY"
    patient_id: Optional[str] = None
    patient_type: Optional[str] = None
    identity_fields: IdentityFields = field(default_factory=dict)
    lookup_status: Optional[str] = None
    lookup_attempts: int = 0
    last_reply: str = ""
    proposed_slot: Optional[dict[str, Any]] = None
    appointment_id: Optional[str] = None
    session_ended: bool = False
    emergency_triggered: bool = False
    emergency_reason_class: Optional[str] = None
    messages: list[BaseMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    utterance_count: int = 0
