import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.conversation import ConversationState
from backend.rag_utils import RAGSystem


class TurnPlanningTests(unittest.TestCase):
    def setUp(self):
        self.rag = RAGSystem.__new__(RAGSystem)
        self.rag.state = ConversationState(last_user_query="Wie ist die Leerlaufspannung bei 25 Grad?",
                                            last_topic_summary="Leerlaufspannung des PV-Moduls")
        self.rag.chat_model = "test"
        self.rag.client = Mock()

    def response(self, kind, query=""):
        self.rag.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"turn_type": kind, "query": query})))])

    def test_route_and_rewrite_share_exactly_one_call(self):
        self.response("FOLLOW_UP", "Wie verändert sich die Leerlaufspannung bei Kälte?")
        query = "Bei Kälte?"
        self.assertEqual(self.rag.detect_turn_type(query), "FOLLOW_UP")
        self.assertIn("Suchfrage:", self.rag.build_follow_up_query(query))
        self.rag.client.chat.completions.create.assert_called_once()
        self.assertEqual(self.rag.state.last_metrics["calls"][0]["stage"], "plan_turn")

    def test_new_topic_overrides_keyword_heuristic(self):
        self.response("NEW_QUESTION")
        self.assertEqual(self.rag.detect_turn_type("Und was ist mit der LWL-Prüfung?"), "NEW_QUESTION")
        self.assertEqual(self.rag.state.turn_plan["query"], "")

    def test_invalid_json_uses_local_fallback_without_second_call(self):
        self.rag.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="not JSON"))])
        self.assertEqual(self.rag.detect_turn_type("Und bei Kälte?"), "FOLLOW_UP")
        self.assertIn("Vorherige Frage:", self.rag.build_follow_up_query("Und bei Kälte?"))
        self.rag.client.chat.completions.create.assert_called_once()

    def test_first_question_needs_no_routing_model(self):
        self.rag.state = ConversationState()
        self.assertEqual(self.rag.detect_turn_type("Was ist UOC?"), "NEW_QUESTION")
        self.rag.client.chat.completions.create.assert_not_called()

    def test_new_numeric_condition_discards_query_but_keeps_route(self):
        self.response("FOLLOW_UP", "Wie ist die Spannung bei -25 Grad?")
        self.assertEqual(self.rag.detect_turn_type("Bei Kälte?"), "FOLLOW_UP")
        self.assertEqual(self.rag.state.turn_plan["query"], "")

    def test_ask_clears_cached_plan_even_for_repeated_input(self):
        self.response("FOLLOW_UP", "Wie verändert sich die Leerlaufspannung bei Kälte?")
        self.rag.handle_follow_up = Mock(return_value="quoted answer")
        self.rag.is_smalltalk = Mock(return_value=False)
        with patch.dict("os.environ", {"RAG_LOG_METRICS": "0"}):
            self.rag.ask("Bei Kälte?")
            self.rag.ask("Bei Kälte?")
        self.assertEqual(self.rag.client.chat.completions.create.call_count, 2)

    def test_valid_new_question_is_forwarded_unchanged(self):
        self.response("NEW_QUESTION")
        self.rag.handle_new_question = Mock(return_value="quoted answer")
        self.rag.is_smalltalk = Mock(return_value=False)
        query = "Was bedeutet N beim Transformator?"
        with patch.dict("os.environ", {"RAG_LOG_METRICS": "0"}):
            self.rag.ask(query)
        self.rag.handle_new_question.assert_called_once_with(query)


if __name__ == "__main__":
    unittest.main()
