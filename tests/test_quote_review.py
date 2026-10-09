"""Contract tests with simulated model outputs, not a live quality benchmark."""
import unittest
import json
import re
from types import SimpleNamespace
from unittest.mock import Mock

from backend.conversation import ConversationState
from backend.rag_utils import RAGSystem
from test_context_windows import segment


def response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class QuoteReviewTests(unittest.TestCase):
    def setUp(self):
        self.rag = RAGSystem.__new__(RAGSystem)
        self.rag.state = ConversationState()
        self.rag.client = Mock()
        self.rag.chat_model = "test"
        self.rag.min_similarity_score = 0.3
        self.rag.summarize_topic = Mock(return_value="Test")
        self.candidates = [dict(segment(i, text=text), score=0.8) for i, text in enumerate([
            "Jetzt berechnen wir die Spannung.",
            "Das folgende Ergebnis gilt nur im gezeigten Beispiel bei 25 Grad Celsius.",
            "In diesem Beispiel betraegt die Spannung 600 Volt.",
            "Wir wechseln jetzt zum Thema Airmass.",
        ])]

    def outputs(self, *values):
        outputs = list(values)
        if len(outputs) > 1 and re.fullmatch(r"\d+(?:,\d+)*", outputs[1]):
            selected = [int(i) for i in outputs[1].split(",")]
            outputs[1] = json.dumps({"selected": selected, "evidence": [
                {"source": i, "span": self.candidates[i-1]["text"]}
                for i in selected if 1 <= i <= len(self.candidates)]})
        self.rag.client.chat.completions.create.side_effect = [response(v) for v in outputs]

    def test_review_removes_extras_but_keeps_condition_and_value(self):
        self.outputs("1,2,3,4", "3,2")
        answer = self.rag.answer_specific_question("Wie hoch ist die Beispielspannung?", self.candidates)
        self.assertEqual([c["text"] for c in self.rag.state.last_citations],
                         [c["text"] for c in self.candidates[1:3]])
        self.assertNotIn(self.candidates[0]["text"], answer)
        self.assertNotIn(self.candidates[3]["text"], answer)
        self.assertEqual(self.rag.client.chat.completions.create.call_count, 2)

    def test_review_can_replace_announcement_with_available_answer(self):
        self.outputs("1", "2,3")
        selected = self.rag.select_relevant_quotes("Wie hoch?", self.candidates)
        self.assertEqual(selected, [2, 3])
        prompt = self.rag.client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("Vorlaeufiger Vorschlag (Quellen-Nummern): 1", prompt)
        for candidate in self.candidates:
            self.assertIn(candidate["text"], prompt)

    def test_inadequate_review_never_falls_back_to_original_quote(self):
        self.outputs("1", "NONE")
        self.rag.state.last_citations = [{"text": "Stale previous answer"}]
        answer = self.rag.answer_specific_question("Wie hoch?", self.candidates[:1])
        self.assertNotIn("Zitat:", answer)
        self.assertIn("kein ausreichendes Zitat", answer)
        self.assertEqual(self.rag.state.last_answer_type, "insufficient_evidence")
        self.assertEqual(self.rag.state.last_citations, [])
        self.rag.summarize_topic.assert_not_called()

    def test_invalid_review_rejects_entire_evidence_set(self):
        for review in ["2,999", "0,3", "Die Antwort ist 600 Volt, Quelle 3", "", "[2,3]"]:
            with self.subTest(review=review):
                self.outputs("2,3", review)
                self.assertEqual(self.rag.select_relevant_quotes("Spannung?", self.candidates), [])

    def test_empty_or_invalid_proposal_gets_independent_review(self):
        for proposal in ["NONE", "2,999", "Es ist Quelle 3"]:
            with self.subTest(proposal=proposal):
                self.rag.client.reset_mock()
                self.outputs(proposal, '{"selected":[],"evidence":[]}')
                self.assertEqual(self.rag.select_relevant_quotes("Spannung?", self.candidates), [])
                self.assertEqual(self.rag.client.chat.completions.create.call_count, 2)

    def test_empty_proposal_can_recover_from_available_evidence(self):
        self.outputs('NONE', '2,3')
        self.assertEqual(self.rag.select_relevant_quotes('Wie hoch?', self.candidates), [2,3])

    def test_nonliteral_span_gets_one_validated_repair(self):
        bad = json.dumps({'selected':[3], 'evidence':[{'source':3,'span':'Invented text'}]})
        good = json.dumps({'selected':[2,3], 'evidence':[{'source':3,'span':self.candidates[2]['text']}]})
        self.outputs('3', bad, good)
        self.assertEqual(self.rag.select_relevant_quotes('Wie hoch?', self.candidates), [2,3])
        self.assertEqual(self.rag.client.chat.completions.create.call_count, 3)

    def test_invalid_repair_does_not_loop_or_release_unchecked_answer(self):
        bad = json.dumps({'selected':[3], 'evidence':[{'source':3,'span':'Invented text'}]})
        self.outputs('3', bad, bad)
        self.assertEqual(self.rag.select_relevant_quotes('Wie hoch?', self.candidates), [])
        self.assertEqual(self.rag.client.chat.completions.create.call_count, 3)

    def test_deliberate_review_abstention_is_not_retried(self):
        self.outputs('3', '{"selected":[],"evidence":[]}')
        self.assertEqual(self.rag.select_relevant_quotes('Wie hoch?', self.candidates), [])
        self.assertEqual(self.rag.client.chat.completions.create.call_count, 2)

    def test_provider_error_does_not_release_unreviewed_selection(self):
        self.rag.client.chat.completions.create.side_effect = [response("2,3"), RuntimeError("provider unavailable")]
        with self.assertRaises(RuntimeError):
            self.rag.answer_specific_question("Spannung?", self.candidates)
        self.assertEqual(self.rag.state.last_citations, [])

    def test_rejected_local_topic_quote_triggers_global_search(self):
        local = dict(segment(0, text='Kurzschlussstrom und Leerlaufspannung sind Teil der Kennlinie.'), score=.8)
        answer = dict(segment(0, filename='other-video.txt', text='Beim Kurzschluss haben wir null Volt.'), score=.7)
        self.rag.chunks = [local, answer]
        self.rag.retrieval_top_k = 16
        self.rag.state.last_selected_chunks = [local]
        self.rag.retrieve = Mock(return_value=[answer])
        self.rag.classify_request_with_context = Mock(return_value='DOMAIN_SPECIFIC')
        self.rag.client.chat.completions.create.side_effect = [
            response('1'), response(json.dumps({'selected':[1], 'evidence':[{'source':1,'span':local['text']}]})),
            response('1'), response(json.dumps({'selected':[1], 'evidence':[{'source':1,'span':answer['text']}]})),
        ]
        result = self.rag.handle_follow_up('Wie groß ist die Spannung beim Kurzschluss?')
        self.rag.retrieve.assert_called_once()
        self.assertIn(answer['text'], result)
        self.assertNotIn(local['text'], result)


if __name__ == "__main__":
    unittest.main()
