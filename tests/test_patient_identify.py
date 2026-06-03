import unittest
from typing import Any

from langchain_core.messages import AIMessage

from src.orchestrator.call_state import default_call_state
from src.orchestrator.graph import build_graph
from src.orchestrator.routing import apply_lookup_routing
from src.orchestrator.tools.lookup_patient import (
    lookup_patient,
    normalize_dob,
    normalize_phone,
    phone_lookup_variants,
    split_full_name,
)


class _MockLookupClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def query_patients(
        self,
        first_name: str,
        last_name: str,
        dob: str,
        phone_variants: list[str],
    ) -> list[dict[str, Any]]:
        return self._rows


class TestLookupPatient(unittest.TestCase):
    def test_split_full_name(self):
        self.assertEqual(split_full_name("Keisha Kris"), ("Keisha", "Kris"))
        self.assertEqual(split_full_name("Mary Jane Watson"), ("Mary Jane", "Watson"))

    def test_normalize_dob_and_phone(self):
        self.assertEqual(normalize_dob("03/15/1989"), "1989-03-15")
        self.assertEqual(normalize_phone("1-555-332-5138"), "5553325138")
        self.assertIn("555-332-5138", phone_lookup_variants("5553325138"))

    def test_lookup_returns_count_and_id(self):
        client = _MockLookupClient([{"id": "patient-abc"}])
        result = lookup_patient(
            first_name="Keisha",
            last_name="Kris",
            dob="1989-03-15",
            phone="555-332-5138",
            client=client,
        )
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["patient_id"], "patient-abc")

    def test_lookup_zero_rows(self):
        client = _MockLookupClient([])
        result = lookup_patient(
            first_name="Wrong",
            last_name="Person",
            dob="2000-01-01",
            phone="555-000-0000",
            client=client,
        )
        self.assertEqual(result["count"], 0)
        self.assertNotIn("patient_id", result)


class TestLookupRouting(unittest.TestCase):
    def test_matched_routes_to_verify(self):
        state = default_call_state("routing-test")
        state["patient_type"] = "returning"
        updated = apply_lookup_routing(state, {"count": 1, "patient_id": "p-1"})
        self.assertEqual(updated["active_node"], "VERIFY_RETURNING")
        self.assertEqual(updated["lookup_status"], "matched")
        self.assertEqual(updated["patient_id"], "p-1")

    def test_not_found_returning_stays_with_retry(self):
        state = default_call_state("routing-test")
        state["patient_type"] = "returning"
        updated = apply_lookup_routing(state, {"count": 0})
        self.assertEqual(updated["active_node"], "PATIENT_IDENTIFY")
        self.assertEqual(updated["lookup_attempts"], 1)

    def test_not_found_new_routes_to_register(self):
        state = default_call_state("routing-test")
        state["patient_type"] = "new"
        updated = apply_lookup_routing(state, {"count": 0})
        self.assertEqual(updated["active_node"], "REGISTER_SHELL_PROFILE")

    def test_ambiguous_stays(self):
        state = default_call_state("routing-test")
        updated = apply_lookup_routing(
            state, {"count": 2, "patient_id": "p-1"}
        )
        self.assertEqual(updated["active_node"], "PATIENT_IDENTIFY")
        self.assertEqual(updated["lookup_status"], "ambiguous")


class TestPatientIdentifyGraph(unittest.IsolatedAsyncioTestCase):
    async def test_lookup_tool_routes_to_verify_stub(self):
        class _ToolLLM:
            def bind_tools(self, tools):
                self._tools = tools
                return self

            def invoke(self, messages):
                if any(type(m).__name__ == "ToolMessage" for m in messages):
                    return AIMessage(content="Thanks, I found your record.")
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "lookup_patient",
                            "args": {
                                "first_name": "Keisha",
                                "last_name": "Kris",
                                "dob": "1989-03-15",
                                "phone": "555-332-5138",
                            },
                            "id": "call-1",
                        }
                    ],
                )

        client = _MockLookupClient([{"id": "patient-abc"}])
        graph = build_graph(llm=_ToolLLM(), lookup_client=client)
        state = default_call_state("identify-graph-test")
        state["user_text"] = "Keisha Kris, March 15 1989, 555-332-5138"
        state["patient_type"] = "returning"

        result = await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": "identify-graph-test"}},
        )

        self.assertEqual(result.get("active_node"), "VERIFY_RETURNING")
        self.assertEqual(result.get("patient_id"), "patient-abc")
        self.assertIn("record", result.get("last_reply", "").lower())


if __name__ == "__main__":
    unittest.main()
