from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.logger import logger
from src.orchestrator.graph import SYSTEM_PROMPT, build_graph

_sessions: dict[str, list] = {}
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def clear_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


async def handle_transcript(event: dict) -> str:
    """Gateway assistant_handler: STT text in, spoken reply out."""
    session_id = event.get("session_id") or "default"
    text = (event.get("text") or "").strip()
    if not text:
        return ""

    if session_id not in _sessions:
        _sessions[session_id] = [SystemMessage(content=SYSTEM_PROMPT)]

    _sessions[session_id].append(HumanMessage(content=text))

    try:
        result = await _get_graph().ainvoke({"messages": _sessions[session_id]})
        messages = result["messages"]
        _sessions[session_id] = messages
        last = messages[-1]
        if isinstance(last, AIMessage):
            return (last.content or "").strip()
        return str(last.content if hasattr(last, "content") else last).strip()
    except Exception as e:
        logger.error(f"Orchestrator LLM error for {session_id}: {e}")
        return "I'm sorry, I'm having trouble right now. Please try again in a moment."
