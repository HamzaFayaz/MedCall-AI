import os
from typing import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

SYSTEM_PROMPT = """You are the automated voice receptionist for Mercy General Hospital in Seattle.
Keep replies short (1-3 sentences) for spoken conversation.
You help with scheduling, registration, and general front-desk questions.
Do not diagnose, prescribe, or give medical advice.
If the caller describes chest pain, difficulty breathing, severe bleeding, or similar emergencies, tell them to hang up and dial 911 immediately."""


class OrchestratorState(TypedDict):
    messages: list[BaseMessage]


def build_graph():
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        api_key=api_key,
        temperature=0.4,
    )

    def chat(state: OrchestratorState) -> OrchestratorState:
        response = llm.invoke(state["messages"])
        return {"messages": state["messages"] + [response]}

    builder = StateGraph(OrchestratorState)
    builder.add_node("chat", chat)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)
    return builder.compile()
