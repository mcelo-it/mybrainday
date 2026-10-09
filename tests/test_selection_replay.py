import copy
import unittest
from unittest.mock import Mock
from types import SimpleNamespace
from backend.conversation import ConversationState
from backend.rag_utils import RAGSystem
from evaluation.replay_selection import prepare_cases, run_replay
from test_context_windows import segment


class SelectionReplayTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [dict(segment(i, text='Original '+str(i)), score=.8) for i in range(2)]
        self.case = {'id':'compare', 'question':'Compare?', 'evidence_sets':[self.chunks]}
        self.dataset = {'cases':[self.case]}
        self.report = {'expected_revision':'rev', 'health_before':{'revision':'rev'},
            'health_after':{'revision':'rev'}, 'cases':[{'id':'compare','question':'Compare?',
                'diagnostics':{'trace':[{'stage':'selection','truncated':False,'sources':[
                    {'number':i, 'filename':c['filename'], 'time_range':c['time_range'], 'score':.8}
                    for i,c in enumerate(self.chunks,1)]}]}}]}

    def prepare(self):
        return prepare_cases(self.dataset,self.chunks,self.report,'rev')

    def test_candidate_order_text_and_scores_reconstructed(self):
        self.assertEqual(self.prepare(), [(self.case,self.chunks)])

    def test_incomplete_or_changed_input_rejected(self):
        for mutate in [
            lambda r:r['health_after'].update(revision='other'),
            lambda r:r['cases'][0].update(question='changed'),
            lambda r:r['cases'][0]['diagnostics']['trace'][0].update(truncated=True),
            lambda r:r['cases'][0]['diagnostics']['trace'][0]['sources'][0].update(number=5),
        ]:
            with self.subTest(mutate=mutate):
                report=copy.deepcopy(self.report)
                mutate(report)
                with self.assertRaises(ValueError):
                    prepare_cases(self.dataset,self.chunks,report,'rev')

    def test_variants_receive_same_candidates_and_fresh_state(self):
        instances=[]
        def factory():
            rag=RAGSystem.__new__(RAGSystem)
            rag.state=ConversationState()
            rag.chat_model="test"
            rag._chat_completion=Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content='{"selected":["Q1-P1","Q2-P1"]}'))]))
            rag.select_relevant_quotes=Mock(return_value=[1])
            rag.review_quote_sufficiency=Mock(return_value=[1,2])
            instances.append(rag)
            return rag
        report=run_replay(self.prepare(),self.chunks,factory)
        self.assertTrue(report['completed'])
        a,b,c=report['results']
        self.assertEqual(c['variant'], 'passage_ids')
        self.assertEqual(c['candidate_sha256'], a['candidate_sha256'])
        self.assertEqual([p['text'] for p in c['passage_quotes']], [x['text'] for x in self.chunks])
        self.assertEqual(c['evaluation_scope'], 'parent_source_segments')
        self.assertEqual(a['candidate_sha256'],b['candidate_sha256'])
        self.assertFalse(a['evaluation']['complete_evidence'])
        self.assertTrue(b['evaluation']['complete_evidence'])
        self.assertIsNot(instances[0].state,instances[1].state)
        instances[1].review_quote_sufficiency.assert_called_once_with('Compare?',self.chunks,[])
        instances[1].select_relevant_quotes.assert_not_called()

    def test_exception_stops_without_retry_or_exposing_raw_error(self):
        factory=Mock(side_effect=RuntimeError('PRIVATE KEY'))
        report=run_replay(self.prepare(),self.chunks,factory)
        self.assertFalse(report['completed'])
        self.assertEqual(factory.call_count,1)
        self.assertNotIn('PRIVATE KEY',str(report))
