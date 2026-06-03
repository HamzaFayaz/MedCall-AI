from langchain_core.messages import AIMessage

from src.orchestrator.call_state import CallState


def register_shell_profile(state: CallState) -> CallState:
    """Stub: full REGISTER_SHELL_PROFILE build is a later sub-plan."""
    reply = (
        "I'll help you register as a new patient. Full registration "
        "is coming in a later step."
    )
    state["last_reply"] = reply
    messages = list(state.get("messages") or [])
    messages.append(AIMessage(content=reply))
    state["messages"] = messages
    return state
