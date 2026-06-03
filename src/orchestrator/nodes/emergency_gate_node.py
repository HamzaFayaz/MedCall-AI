from src.orchestrator.call_state import CallState
from src.orchestrator.emergency_gate import check_emergency, log_emergency_triggered


def emergency_gate_node(state: CallState) -> CallState:
    text = (state.get("user_text") or "").strip()
    if not text or state.get("session_ended"):
        return state

    result = check_emergency(text)
    if result.triggered:
        reason = result.reason_class or "unknown"
        session_id = state.get("session_id", "default")
        log_emergency_triggered(session_id, reason)
        state["emergency_triggered"] = True
        state["emergency_reason_class"] = reason
        state["session_ended"] = True
        state["active_node"] = "ENDED"
    return state
