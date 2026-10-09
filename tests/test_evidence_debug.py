import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from backend.evidence import validate_review
from backend.conversation import ConversationState
from backend.rag_utils import RAGSystem
from test_context_windows import segment


class EvidenceDebugTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [dict(segment(0, text='Original A')), dict(segment(1, text='Original B'))]
        self.raw = json.dumps({'selected':[1], 'evidence':[{'source':1,'span':'Original B'}]})

    def test_default_diagnostics_contain_no_text(self):
        indices, diagnostic = validate_review(self.raw, self.candidates, 'Question')
        self.assertEqual(indices, [])
        self.assertNotIn('mismatch', diagnostic)
        self.assertNotIn('Original', str(diagnostic))

    def test_opt_in_compares_assigned_source_and_finds_other_candidate(self):
        indices, diagnostic = validate_review(self.raw, self.candidates, 'Question', capture_mismatch=True)
        self.assertEqual(indices, [])
        mismatch = diagnostic['mismatch']
        self.assertEqual(mismatch['model_span'], 'Original B')
        self.assertEqual(mismatch['original_text'], 'Original A')
        self.assertEqual(mismatch['matching_candidate_numbers'], [2])
        self.assertEqual(mismatch['source'], 1)

    def test_capture_is_bounded_without_changing_validation(self):
        self.candidates[0]['text'] = 'A' * 7000
        raw = json.dumps({'selected':[1], 'evidence':[{'source':1,'span':'B'*3000}]})
        indices, diagnostic = validate_review(raw, self.candidates, 'Question', capture_mismatch=True)
        self.assertEqual(indices, [])
        mismatch = diagnostic['mismatch']
        self.assertEqual(len(mismatch['model_span']), 2000)
        self.assertEqual(len(mismatch['original_text']), 6000)
        self.assertTrue(mismatch['model_span_truncated'])
        self.assertTrue(mismatch['original_text_truncated'])

    def test_rag_requires_both_flags_and_preserves_rejection(self):
        for diagnostics, debug in [(False,False),(True,False),(False,True),(True,True)]:
            rag = RAGSystem.__new__(RAGSystem)
            rag.state = ConversationState(diagnostics_enabled=diagnostics, evidence_debug_enabled=debug)
            rag.chat_model = 'test'
            rag.client = Mock()
            rag.client.chat.completions.create.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=self.raw))])
            self.assertEqual(rag.review_quote_sufficiency('Question', self.candidates, [1]), [])
            if diagnostics:
                self.assertEqual('mismatch' in rag.state.last_trace[-1]['validation'], debug)
            else:
                self.assertEqual(rag.state.last_trace, [])
