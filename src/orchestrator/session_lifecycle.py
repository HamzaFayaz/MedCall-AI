from langchain_core.messages import SystemMessage

from src.logger import logger
from src.orchestrator.graph import SYSTEM_PROMPT
from src.orchestrator.state import OrchestratorSessionState

_sessions: dict[str, OrchestratorSessionState] = {}


def start_session(session_id: str) -> OrchestratorSessionState:
    """Bootstrap orchestrator state once per call (idempotent)."""
    existing = _sessions.get(session_id)
    if existing is not None:
        return existing

    state = OrchestratorSessionState(
        session_id=session_id,
        active_node="PATIENT_IDENTIFY",
        messages=[SystemMessage(content=SYSTEM_PROMPT)],
    )
    _sessions[session_id] = state
    logger.info(f"session.started session_id={session_id}")
    return state


def get_session(session_id: str) -> OrchestratorSessionState | None:
    return _sessions.get(session_id)


def end_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def clear_session(session_id: str) -> None:
    """Gateway cleanup hook (alias for end_session)."""
    end_session(session_id)
