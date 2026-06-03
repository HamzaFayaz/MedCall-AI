from src.logger import logger
from src.orchestrator.call_state import CallState
from src.orchestrator.prompts import build_system_content


def session_start(state: CallState) -> CallState:
    """Bootstrap call state once per thread (idempotent)."""
    session_id = state.get("session_id", "default")
    if not state.get("messages"):
        active = state.get("active_node", "PATIENT_IDENTIFY")
        from langchain_core.messages import SystemMessage

        state["messages"] = [SystemMessage(content=build_system_content(active))]
        state["active_node"] = active
        logger.info(f"session.started session_id={session_id}")
    return state
