from src.logger import logger
from src.orchestrator.call_state import apply_call_state_to_session
from src.orchestrator.graph import get_compiled_graph
from src.orchestrator.session_lifecycle import (
    clear_session,
    end_session,
    get_session,
    start_session,
)


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

    config = {"configurable": {"thread_id": session_id}}
    call_input = {"user_text": text, "session_id": session_id}

    try:
        result = await get_compiled_graph().ainvoke(call_input, config=config)
        apply_call_state_to_session(state, result)
        return (result.get("last_reply") or "").strip()
    except Exception as e:
        logger.error(f"Orchestrator graph error for {session_id}: {e}")
        return "I'm sorry, I'm having trouble right now. Please try again in a moment."


__all__ = [
    "clear_session",
    "end_session",
    "handle_transcript",
    "start_session",
    "get_session",
]
