import unittest
import json
from types import SimpleNamespace
from unittest.mock import Mock

from backend.conversation import ConversationState
from backend.rag_utils import RAGSystem
from evaluation.check_deployment import reference_trace
from test_context_windows import segment


def response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class SourceTraceTests(unittest.TestCase):
    def setUp(self):
        self.rag = RAGSystem.__new__(RAGSystem)
        self.rag.state = ConversationState(diagnostics_enabled=True)
        self.rag.chat_model = 'test'
        self.rag.client = Mock()
        self.candidates = [dict(segment(i, text='PRIVATE SOURCE '+str(i)), score=.8) for i in range(3)]

    def test_selection_and_review_record_actual_replacement(self):
        self.rag.client.chat.completions.create.side_effect = [response('1'), response(json.dumps({'selected':[2,3], 'evidence':[{'source':2,'span':self.candidates[1]['text']}]}))]
        self.assertEqual(self.rag.select_relevant_quotes('PRIVATE QUESTION', self.candidates), [2, 3])
        trace = self.rag.state.last_trace
        self.assertEqual([e['stage'] for e in trace], ['selection', 'review'])
        self.assertEqual([e['selected'] for e in trace], [[1], [2, 3]])
        self.assertNotIn('PRIVATE', str(trace))
        ref = (self.candidates[1]['filename'], self.candidates[1]['time_range'])
        result = reference_trace({'trace': trace}, ref)
        self.assertTrue(result['stages'][0]['reference_present'])
        self.assertFalse(result['stages'][0]['reference_selected'])
        self.assertTrue(result['stages'][1]['reference_selected'])

    def test_review_rejection_records_reason_without_model_text(self):
        self.rag.client.chat.completions.create.return_value = response(json.dumps({
            'selected':[1], 'evidence':[{'source':1, 'span':'PRIVATE invented text'}]}))
        self.assertEqual(self.rag.review_quote_sufficiency('Question', self.candidates, [1]), [])
        event = self.rag.state.last_trace[-1]
        self.assertEqual(event['selected'], [])
        self.assertEqual(event['validation']['proposed'], [1])
        self.assertEqual(event['validation']['status'], 'span_not_in_source')
        self.assertEqual(event['stage'], 'review_repair')
        self.assertEqual(len(self.rag.state.last_trace), 2)
        self.assertNotIn('PRIVATE', str(event))

    def test_whitespace_review_preserves_original_answer(self):
        self.candidates[0]['text'] = 'Dämpfung. \n\nDann Durchgängigkeit.'
        self.rag.client.chat.completions.create.return_value = response(json.dumps({
            'selected':[1], 'evidence':[{'source':1, 'span':'Dämpfung. Dann Durchgängigkeit.'}]}))
        indices = self.rag.review_quote_sufficiency('Welche Verfahren?', self.candidates, [1])
        self.assertEqual(indices, [1])
        answer = self.rag.construct_answer_from_chunks([self.candidates[0]])
        self.assertIn(self.candidates[0]['text'], answer)
        self.assertTrue(self.rag.state.last_trace[-1]['validation']['whitespace_normalized'])

    def test_empty_proposal_is_reviewed_and_still_rejected(self):
        self.rag.client.chat.completions.create.return_value = response('NONE')
        self.assertEqual(self.rag.select_relevant_quotes('Question', self.candidates), [])
        self.assertEqual(len(self.rag.state.last_trace), 2)
        self.assertEqual(self.rag.state.last_trace[0]['selected'], [])

    def test_trace_disabled_by_default(self):
        self.rag.state = ConversationState()
        self.rag.trace_sources('retrieval', self.candidates)
        self.assertEqual(self.rag.state.last_trace, [])

    def test_limits_are_explicit(self):
        for _ in range(20):
            self.rag.trace_sources('retrieval', self.candidates * 20)
        self.assertEqual(len(self.rag.state.last_trace), 16)
        self.assertEqual(len(self.rag.state.last_trace[0]['sources']), 40)
        self.assertTrue(self.rag.state.last_trace[0]['truncated'])

    def test_turn_reset_and_session_isolation(self):
        self.rag.trace_sources('retrieval', self.candidates)
        other = self.rag.for_conversation(ConversationState())
        self.rag._ask = Mock(return_value='answer')
        self.rag.ask('Question')
        self.assertEqual(self.rag.state.last_trace, [])
        self.assertEqual(other.state.last_trace, [])
        self.assertFalse(other.state.diagnostics_enabled)

    def test_missing_diagnostics_is_not_negative_retrieval_evidence(self):
        self.assertEqual(reference_trace(None, ('file', 'time')), {'available': False})


if __name__ == '__main__':
    unittest.main()
