import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from backend.conversation import ConversationState
from backend.rag_utils import RAGSystem


class FollowupQueryTests(unittest.TestCase):
    def setUp(self):
        self.rag = RAGSystem.__new__(RAGSystem)
        self.rag.state = ConversationState(last_user_query="Wie verändert sich die Leerlaufspannung eines PV-Moduls?",
                                            last_topic_summary="Leerlaufspannung und Temperatur")
        self.rag.chat_model = "test"
        self.rag.client = Mock()

    def output(self, raw):
        self.rag.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=raw))])

    def test_resolved_query_preserves_original_followup(self):
        self.output(json.dumps({"resolved": True, "query": "Wie verändert sich die Leerlaufspannung bei niedriger Temperatur?"}))
        result = self.rag.build_follow_up_query("Und bei niedriger Temperatur?")
        self.assertIn("Suchfrage: Wie verändert sich die Leerlaufspannung", result)
        self.assertIn("Originale Folgefrage: Und bei niedriger Temperatur?", result)
        self.rag.client.chat.completions.create.assert_called_once()

    def test_unknown_or_invalid_output_uses_context_fallback(self):
        for value in ['{"resolved":false,"query":""}', 'freie Antwort', '[]',
                      '{"resolved":"true","query":"Frage"}', '{"resolved":true,"query":""}']:
            with self.subTest(value=value):
                self.output(value)
                result = self.rag.build_follow_up_query("Und dort?")
                self.assertIn("Vorherige Frage:", result)
                self.assertIn("Folgefrage: Und dort?", result)

    def test_new_numeric_condition_is_rejected(self):
        self.output('{"resolved":true,"query":"Wie hoch ist die Spannung bei -20 Grad?"}')
        result = self.rag.build_follow_up_query("Und bei Kälte?")
        self.assertNotIn("20", result)
        self.assertIn("Folgefrage: Und bei Kälte?", result)

    def test_without_context_no_model_call(self):
        self.rag.state = ConversationState()
        self.assertEqual(self.rag.build_follow_up_query("Warum?"), "Warum?")
        self.rag.client.chat.completions.create.assert_not_called()

    def test_context_is_bounded_and_original_constraints_are_not_truncated(self):
        self.rag.state.last_effective_query = "A" * 9000
        self.rag.state.last_topic_summary = "B" * 9000
        question = "C" * 2000
        result = self.rag.build_follow_up_query(question)
        self.assertIn(question, result)
        self.assertLess(len(result), 4100)
        self.rag.client.chat.completions.create.assert_not_called()

    def test_fallback_does_not_nest_previous_fallback(self):
        self.rag.state.last_effective_query = "Vorherige Frage: OLD\nFolgefrage: OLDER"
        self.output("invalid")
        self.assertNotIn("OLD", self.rag.build_follow_up_query("Warum?"))


if __name__ == "__main__":
    unittest.main()
