from langchain_core.messages import AIMessage

from src.orchestrator.call_state import CallState


def verify_returning(state: CallState) -> CallState:
    """Stub: full VERIFY_RETURNING build is a later sub-plan."""
    reply = (
        "Thanks — I found your record. Identity verification will continue "
        "in the next step (not built yet)."
    )
    state["last_reply"] = reply
    messages = list(state.get("messages") or [])
    messages.append(AIMessage(content=reply))
    state["messages"] = messages
    return state
