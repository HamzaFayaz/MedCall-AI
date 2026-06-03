import unittest

from langchain_core.messages import HumanMessage

from src.orchestrator.session_lifecycle import (
    clear_session,
    end_session,
    get_session,
    start_session,
)


class TestSessionLifecycle(unittest.TestCase):
    def setUp(self):
        clear_session("test-session-a")
        clear_session("test-session-b")

    def tearDown(self):
        clear_session("test-session-a")
        clear_session("test-session-b")

    def test_start_session_initializes_state(self):
        state = start_session("test-session-a")
        self.assertEqual(state.session_id, "test-session-a")
        self.assertEqual(state.active_node, "PATIENT_IDENTIFY")
        self.assertIsNone(state.patient_id)
        self.assertFalse(state.session_ended)
        self.assertFalse(state.emergency_triggered)
        self.assertEqual(len(state.messages), 0)
        self.assertEqual(state.lookup_attempts, 0)

    def test_get_session_returns_started_state(self):
        start_session("test-session-a")
        loaded = get_session("test-session-a")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.session_id, "test-session-a")

    def test_idempotent_start_preserves_mid_call_state(self):
        state = start_session("test-session-a")
        state.utterance_count = 3
        state.messages.append(HumanMessage(content="hello"))
        state.patient_id = "patient-123"

        again = start_session("test-session-a")
        self.assertIs(again, state)
        self.assertEqual(again.utterance_count, 3)
        self.assertEqual(again.patient_id, "patient-123")
        self.assertEqual(len(again.messages), 1)

    def test_end_session_clears_state(self):
        start_session("test-session-a")
        end_session("test-session-a")
        self.assertIsNone(get_session("test-session-a"))

    def test_clear_session_alias(self):
        start_session("test-session-b")
        clear_session("test-session-b")
        self.assertIsNone(get_session("test-session-b"))


if __name__ == "__main__":
    unittest.main()
