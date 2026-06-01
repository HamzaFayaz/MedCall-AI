from langchain_core.messages import AIMessage, HumanMessage

from src.logger import logger
from src.orchestrator.emergency_gate import (
    EMERGENCY_SCRIPT,
    check_emergency,
    log_emergency_triggered,
)
from src.orchestrator.graph import build_graph
from src.orchestrator.session_lifecycle import (
    clear_session,
    end_session,
    get_session,
    start_session,
)

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def handle_transcript(event: dict) -> str:
    """Gateway assistant_handler: STT text in, spoken reply out."""
    session_id = event.get("session_id") or "default"
    text = (event.get("text") or "").strip()
    if not text:
        return ""

    state = get_session(session_id)
    if state is None:
        state = start_session(session_id)

    if state.session_ended:
        return ""

    emergency = check_emergency(text)
    if emergency.triggered:
        reason = emergency.reason_class or "unknown"
        log_emergency_triggered(session_id, reason)
        state.emergency_triggered = True
        state.emergency_reason_class = reason
        state.session_ended = True
        state.active_node = "ENDED"
        return EMERGENCY_SCRIPT

    state.utterance_count += 1
    state.messages.append(HumanMessage(content=text))

    try:
        result = await _get_graph().ainvoke({"messages": state.messages})
        messages = result["messages"]
        state.messages = messages
        last = messages[-1]
        if isinstance(last, AIMessage):
            return (last.content or "").strip()
        return str(last.content if hasattr(last, "content") else last).strip()
    except Exception as e:
        logger.error(f"Orchestrator LLM error for {session_id}: {e}")
        return "I'm sorry, I'm having trouble right now. Please try again in a moment."


__all__ = [
    "clear_session",
    "end_session",
    "handle_transcript",
    "start_session",
    "get_session",
]
