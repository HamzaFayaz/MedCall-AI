import os
from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.orchestrator.call_state import CallState
from src.orchestrator.nodes.emergency_gate_node import emergency_gate_node
from src.orchestrator.nodes.patient_identify import make_patient_identify_node
from src.orchestrator.nodes.play_911 import play_911
from src.orchestrator.nodes.register_shell_profile import register_shell_profile
from src.orchestrator.nodes.session_start import session_start
from src.orchestrator.nodes.verify_returning import verify_returning
from src.orchestrator.routing import (
    route_after_emergency,
    route_after_patient_identify,
)

# Back-compat for tests that imported SYSTEM_PROMPT from graph.py
from src.orchestrator.prompts import GLOBAL_PROMPT as SYSTEM_PROMPT


def _create_llm() -> ChatOpenAI:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        api_key=api_key,
        temperature=0.4,
    )


def build_graph(
    llm: Any | None = None,
    lookup_client: Any | None = None,
    checkpointer: Any | None = None,
):
    model = llm or _create_llm()
    memory = checkpointer if checkpointer is not None else MemorySaver()

    builder = StateGraph(CallState)
    builder.add_node("session_start", session_start)
    builder.add_node("emergency_gate", emergency_gate_node)
    builder.add_node("play_911", play_911)
    builder.add_node(
        "patient_identify",
        make_patient_identify_node(model, lookup_client=lookup_client),
    )
    builder.add_node("verify_returning", verify_returning)
    builder.add_node("register_shell_profile", register_shell_profile)

    builder.add_edge(START, "session_start")
    builder.add_edge("session_start", "emergency_gate")
    builder.add_conditional_edges(
        "emergency_gate",
        route_after_emergency,
        {
            "play_911": "play_911",
            "patient_identify": "patient_identify",
            "verify_returning": "verify_returning",
            "register_shell_profile": "register_shell_profile",
            END: END,
        },
    )
    builder.add_edge("play_911", END)

    builder.add_conditional_edges(
        "patient_identify",
        route_after_patient_identify,
        {
            "verify_returning": "verify_returning",
            "register_shell_profile": "register_shell_profile",
            END: END,
        },
    )
    builder.add_edge("verify_returning", END)
    builder.add_edge("register_shell_profile", END)

    return builder.compile(checkpointer=memory)


@lru_cache(maxsize=1)
def get_compiled_graph():
    return build_graph()
