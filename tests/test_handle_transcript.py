import unittest
from unittest.mock import patch

from src.orchestrator import clear_session, handle_transcript, start_session
from src.orchestrator.emergency_gate import EMERGENCY_SCRIPT
from src.orchestrator.graph import build_graph
from src.orchestrator.session_lifecycle import get_session


class TestHandleTranscriptEmergency(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        clear_session("emergency-flow-test")
        from src.orchestrator import graph as graph_module

        graph_module.get_compiled_graph.cache_clear()

    def tearDown(self):
        clear_session("emergency-flow-test")
        from src.orchestrator import graph as graph_module

        graph_module.get_compiled_graph.cache_clear()

    async def test_emergency_returns_script_and_ends_session(self):
        start_session("emergency-flow-test")
        reply = await handle_transcript(
            {
                "session_id": "emergency-flow-test",
                "text": "I have chest pain",
                "type": "transcript.final",
            }
        )
        self.assertEqual(reply, EMERGENCY_SCRIPT)

        state = get_session("emergency-flow-test")
        self.assertIsNotNone(state)
        self.assertTrue(state.session_ended)
        self.assertTrue(state.emergency_triggered)
        self.assertEqual(state.emergency_reason_class, "cardiac")

    async def test_subsequent_utterance_after_emergency_is_silent(self):
        start_session("emergency-flow-test")
        await handle_transcript(
            {"session_id": "emergency-flow-test", "text": "can't breathe"}
        )
        reply = await handle_transcript(
            {"session_id": "emergency-flow-test", "text": "hello?"}
        )
        self.assertEqual(reply, "")

    @patch("src.orchestrator.get_compiled_graph")
    async def test_non_emergency_invokes_graph(self, mock_get_graph):
        from langchain_core.messages import AIMessage

        class _ReplyLLM:
            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                return AIMessage(content="Hello from graph.")

        mock_get_graph.return_value = build_graph(llm=_ReplyLLM())
        start_session("graph-invoke-test")
        reply = await handle_transcript(
            {"session_id": "graph-invoke-test", "text": "hello"}
        )
        self.assertEqual(reply, "Hello from graph.")


if __name__ == "__main__":
    unittest.main()
