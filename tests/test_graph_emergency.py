import unittest

from langchain_core.messages import AIMessage

from src.orchestrator.call_state import default_call_state
from src.orchestrator.graph import build_graph
from src.orchestrator.emergency_gate import EMERGENCY_SCRIPT


class _StubLLM:
    """Emergency path should not invoke the LLM."""

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        raise AssertionError("LLM should not be called on emergency path")


class TestGraphEmergency(unittest.IsolatedAsyncioTestCase):
    async def test_emergency_routes_to_play_911(self):
        graph = build_graph(llm=_StubLLM())
        state = default_call_state("graph-emergency-test")
        state["user_text"] = "I have chest pain"

        result = await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": "graph-emergency-test"}},
        )

        self.assertEqual(result.get("last_reply"), EMERGENCY_SCRIPT)
        self.assertTrue(result.get("emergency_triggered"))
        self.assertTrue(result.get("session_ended"))
        self.assertEqual(result.get("emergency_reason_class"), "cardiac")

    async def test_clear_path_uses_patient_identify_stub_llm(self):
        class _ReplyLLM:
            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                return AIMessage(content="How can I help you today?")

        graph = build_graph(llm=_ReplyLLM())
        state = default_call_state("graph-clear-test")
        state["user_text"] = "I need to schedule an appointment"

        result = await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": "graph-clear-test"}},
        )

        self.assertEqual(result.get("last_reply"), "How can I help you today?")
        self.assertFalse(result.get("emergency_triggered"))


if __name__ == "__main__":
    unittest.main()
