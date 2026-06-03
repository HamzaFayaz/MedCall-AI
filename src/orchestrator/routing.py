from langgraph.graph import END

from src.orchestrator.call_state import CallState

MAX_LOOKUP_ATTEMPTS = 2


def route_after_emergency(state: CallState) -> str:
    if state.get("emergency_triggered"):
        return "play_911"
    return route_active_node(state)


def route_active_node(state: CallState) -> str:
    if state.get("session_ended"):
        return END
    active = state.get("active_node", "PATIENT_IDENTIFY")
    if active == "VERIFY_RETURNING":
        return "verify_returning"
    if active == "REGISTER_SHELL_PROFILE":
        return "register_shell_profile"
    if active == "ENDED":
        return END
    return "patient_identify"


def route_after_patient_identify(state: CallState) -> str:
    active = state.get("active_node", "PATIENT_IDENTIFY")
    if active == "VERIFY_RETURNING":
        return "verify_returning"
    if active == "REGISTER_SHELL_PROFILE":
        return "register_shell_profile"
    return END


def apply_lookup_routing(state: CallState, lookup_result: dict) -> CallState:
    """Code-driven routing after lookup_patient — LLM does not pick next node."""
    count = int(lookup_result.get("count", 0))
    patient_type = (state.get("patient_type") or "").lower()

    if count == 1:
        state["lookup_status"] = "matched"
        state["patient_id"] = lookup_result.get("patient_id")
        state["active_node"] = "VERIFY_RETURNING"
        return state

    if count >= 2:
        state["lookup_status"] = "ambiguous"
        state["active_node"] = "PATIENT_IDENTIFY"
        return state

    state["lookup_status"] = "not_found"
    attempts = int(state.get("lookup_attempts", 0)) + 1
    state["lookup_attempts"] = attempts

    if patient_type == "new":
        state["active_node"] = "REGISTER_SHELL_PROFILE"
        return state

    if patient_type == "returning" and attempts < MAX_LOOKUP_ATTEMPTS:
        state["active_node"] = "PATIENT_IDENTIFY"
        return state

    if patient_type == "returning" and attempts >= MAX_LOOKUP_ATTEMPTS:
        state["active_node"] = "REGISTER_SHELL_PROFILE"
        return state

    state["active_node"] = "PATIENT_IDENTIFY"
    return state
