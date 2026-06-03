from typing import Any, TypedDict

from langchain_core.messages import BaseMessage


class IdentityFields(TypedDict, total=False):
    first_name: str
    last_name: str
    dob: str
    phone: str
    full_name: str


class CallState(TypedDict, total=False):
    """LangGraph state for one voice call (thread_id = session_id)."""

    messages: list[BaseMessage]
    session_ended: bool
    emergency_triggered: bool
    emergency_reason_class: str | None
    active_node: str
    patient_id: str | None
    patient_type: str | None
    identity_fields: IdentityFields
    lookup_status: str | None
    lookup_attempts: int
    last_reply: str
    user_text: str
    utterance_count: int
    session_id: str


def default_call_state(session_id: str) -> CallState:
    return {
        "messages": [],
        "session_ended": False,
        "emergency_triggered": False,
        "emergency_reason_class": None,
        "active_node": "PATIENT_IDENTIFY",
        "patient_id": None,
        "patient_type": None,
        "identity_fields": {},
        "lookup_status": None,
        "lookup_attempts": 0,
        "last_reply": "",
        "user_text": "",
        "utterance_count": 0,
        "session_id": session_id,
    }


def session_to_call_state(session: Any) -> CallState:
    """Map OrchestratorSessionState → CallState for graph invoke."""
    identity = getattr(session, "identity_fields", None) or {}
    return {
        "messages": list(session.messages),
        "session_ended": session.session_ended,
        "emergency_triggered": session.emergency_triggered,
        "emergency_reason_class": session.emergency_reason_class,
        "active_node": session.active_node,
        "patient_id": session.patient_id,
        "patient_type": getattr(session, "patient_type", None),
        "identity_fields": dict(identity),
        "lookup_status": getattr(session, "lookup_status", None),
        "lookup_attempts": getattr(session, "lookup_attempts", 0),
        "last_reply": getattr(session, "last_reply", "") or "",
        "user_text": "",
        "utterance_count": session.utterance_count,
        "session_id": session.session_id,
    }


def apply_call_state_to_session(session: Any, state: CallState) -> None:
    """Sync graph result back to in-memory session store."""
    if "messages" in state:
        session.messages = list(state["messages"])
    session.session_ended = state.get("session_ended", session.session_ended)
    session.emergency_triggered = state.get(
        "emergency_triggered", session.emergency_triggered
    )
    session.emergency_reason_class = state.get(
        "emergency_reason_class", session.emergency_reason_class
    )
    session.active_node = state.get("active_node", session.active_node)
    session.patient_id = state.get("patient_id", session.patient_id)
    session.patient_type = state.get("patient_type", getattr(session, "patient_type", None))
    session.identity_fields = state.get(
        "identity_fields", getattr(session, "identity_fields", {})
    )
    session.lookup_status = state.get(
        "lookup_status", getattr(session, "lookup_status", None)
    )
    session.lookup_attempts = state.get(
        "lookup_attempts", getattr(session, "lookup_attempts", 0)
    )
    session.last_reply = state.get("last_reply", getattr(session, "last_reply", "")) or ""
    session.utterance_count = state.get("utterance_count", session.utterance_count)
