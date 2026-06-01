import unittest

from src.orchestrator.emergency_gate import (
    EMERGENCY_SCRIPT,
    check_emergency,
    normalize_text,
)


class TestNormalizeText(unittest.TestCase):
    def test_collapses_whitespace_and_lowercases(self):
        self.assertEqual(normalize_text("  Chest   PAIN  "), "chest pain")


class TestEmergencyGateMustTrigger(unittest.TestCase):
    def test_chest_pain(self):
        result = check_emergency("I have chest pain")
        self.assertTrue(result.triggered)
        self.assertEqual(result.reason_class, "cardiac")

    def test_trouble_breathing(self):
        result = check_emergency("I'm having trouble breathing")
        self.assertTrue(result.triggered)
        self.assertEqual(result.reason_class, "breathing")

    def test_suicidal_thoughts(self):
        result = check_emergency("I have suicidal thoughts")
        self.assertTrue(result.triggered)
        self.assertEqual(result.reason_class, "suicidal")

    def test_stroke_word_boundary(self):
        result = check_emergency("I think I'm having a stroke")
        self.assertTrue(result.triggered)
        self.assertEqual(result.reason_class, "stroke_neuro")

    def test_911(self):
        result = check_emergency("Please call 911 for me")
        self.assertTrue(result.triggered)
        self.assertEqual(result.reason_class, "call_911")

    def test_severe_bleeding(self):
        result = check_emergency("There is severe bleeding")
        self.assertTrue(result.triggered)
        self.assertEqual(result.reason_class, "bleeding")

    def test_prd_combined_symptoms(self):
        result = check_emergency("I have chest pain and trouble breathing")
        self.assertTrue(result.triggered)

    def test_past_tense_still_triggers_v1(self):
        """v1 policy: no past-tense excludes — bias toward trigger."""
        result = check_emergency("I had chest pain yesterday")
        self.assertTrue(result.triggered)
        self.assertEqual(result.reason_class, "cardiac")


class TestEmergencyGateMustNotTrigger(unittest.TestCase):
    def test_routine_scheduling(self):
        result = check_emergency("I'd like to book an appointment with Dr. Smith")
        self.assertFalse(result.triggered)
        self.assertIsNone(result.reason_class)

    def test_parking_question(self):
        result = check_emergency("Where do I park at the hospital?")
        self.assertFalse(result.triggered)

    def test_stroke_in_unrelated_word(self):
        """Word boundary: 'stroke' inside unrelated tokens should not match."""
        result = check_emergency("I had a heatstroke last summer")
        self.assertFalse(result.triggered)

    def test_empty(self):
        result = check_emergency("   ")
        self.assertFalse(result.triggered)


class TestEmergencyScript(unittest.TestCase):
    def test_prd_script_exact(self):
        self.assertIn("dial 911 immediately", EMERGENCY_SCRIPT)
        self.assertIn("automated assistant", EMERGENCY_SCRIPT)


if __name__ == "__main__":
    unittest.main()
