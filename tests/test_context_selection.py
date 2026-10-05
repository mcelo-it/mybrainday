import unittest
import json
from types import SimpleNamespace
from unittest.mock import Mock

from backend.rag_utils import RAGSystem
from backend.conversation import ConversationState
from test_context_windows import segment


class ContextSelectionTests(unittest.TestCase):
    def setUp(self):
        self.rag = RAGSystem.__new__(RAGSystem)
        self.rag.state = ConversationState()
        self.rag.chunks = [segment(0, text="Das folgende Beispiel gilt für XY."),
                           segment(1, text="Jetzt berechnen wir die Spannung bei XY."),
                           segment(2, text="Im gezeigten Beispiel sind es 600 Volt.")]
        self.rag.retrieval_top_k = 8
        self.rag.min_similarity_score = 0.3
        self.rag.chat_model = "test"
        self.rag.client = Mock()
        self.rag.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="3"))])
        def model_reply(**kwargs):
            raw = self.rag.client.chat.completions.create.return_value.choices[0].message.content
            if raw == "3" and "evidence" in kwargs["messages"][0]["content"]:
                raw = json.dumps({"selected": [3], "evidence": [{"source": 3, "span": self.rag.chunks[2]["text"]}]})
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw))])
        self.rag.client.chat.completions.create.side_effect = model_reply
        self.rag.retrieve = Mock(return_value=[dict(self.rag.chunks[1], score=0.8)])
        self.rag.classify_request_with_context = Mock(return_value="DOMAIN_SPECIFIC")
        self.rag.summarize_topic = Mock(return_value="Spannung bei XY")

    def test_later_result_is_quotable_with_its_own_timestamp(self):
        answer = self.rag.handle_new_question("Wie groß sollte die Spannung bei XY sein?")
        self.assertIn(self.rag.chunks[2]["text"], answer)
        self.assertNotIn(self.rag.chunks[1]["text"], answer)
        self.assertEqual(self.rag.state.last_citations[0]["time_range"], self.rag.chunks[2]["time_range"])
        messages = self.rag.client.chat.completions.create.call_args.kwargs["messages"]
        self.assertIn("keine Antwort", messages[0]["content"])
        self.assertIn("Komponenten der Photovoltaik", messages[1]["content"])
        self.assertIn(self.rag.chunks[0]["text"], messages[1]["content"])
        self.assertIn(self.rag.chunks[2]["text"], messages[1]["content"])

    def test_followup_can_select_neighbour(self):
        self.rag.state.last_selected_chunks = [dict(self.rag.chunks[1], score=0.8)]
        answer = self.rag.handle_follow_up("Wie groß genau?")
        self.assertIn(self.rag.chunks[2]["text"], answer)
        self.rag.retrieve.assert_not_called()

    def test_none_after_clarification_does_not_quote_all_candidates(self):
        self.rag.state.pending_clarification = {
            "original_query": "Spannung", "options": [{"label": "XY", "source_numbers": [1]}],
            "retrieved_chunks": [dict(self.rag.chunks[1], score=0.8)],
        }
        self.rag.resolve_clarification_option = Mock(return_value=0)
        self.rag.client.chat.completions.create.return_value.choices[0].message.content = "NONE"
        answer = self.rag.handle_pending_clarification("1")
        self.assertNotIn("Zitat:", answer)
        self.assertEqual(self.rag.state.last_citations, [])

    def test_unstructured_explanation_is_not_parsed_as_source_number(self):
        self.rag.client.chat.completions.create.return_value.choices[0].message.content = "Es sind 600 Volt, Quelle 1."
        self.assertEqual(self.rag.select_relevant_quotes("Spannung?", [dict(self.rag.chunks[1], score=0.8)]), [])


if __name__ == "__main__":
    unittest.main()
