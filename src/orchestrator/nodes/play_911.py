from src.orchestrator.call_state import CallState
from src.orchestrator.emergency_gate import EMERGENCY_SCRIPT


def play_911(state: CallState) -> CallState:
    state["last_reply"] = EMERGENCY_SCRIPT
    state["session_ended"] = True
    return state
