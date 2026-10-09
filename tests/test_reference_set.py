import copy
import json
import unittest

from backend.citations import citation_from_chunk, format_citation_source
from evaluation.check_reference_set import run_reference_check


class ReferenceSetTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [dict(filename='10 Example.txt', time_range=str(i), text='Original '+str(i),
            module_number='10', module_name='Transformator', video_number='1', video_name='Test')
            for i in range(3)]
        self.dataset = {'status': 'synthetic', 'cases': [
            {'id':'single', 'question':'Single?', 'evidence_sets':[[self.chunks[0]]]},
            {'id':'compare', 'question':'Compare?', 'evidence_sets':[[self.chunks[1],self.chunks[2]]]}]}
        self.calls = []
        self.answers = [self.chunks[:1], self.chunks[1:]]
        self.turn = 0
        self.health = 0
        self.after = 'rev'

    def request(self, path, message=None, token=None):
        self.calls.append((path, message, token))
        if path == '/health':
            self.health += 1
            return {'status':'ok', 'revision':'rev' if self.health == 1 else self.after}
        if path == '/sources':
            self.assertEqual(token, 'PRIVATE_SESSION_'+str(self.turn))
            return self.citations
        self.citations = [citation_from_chunk(c) for c in self.answers[self.turn]]
        self.turn += 1
        return {'conversation_id':'PRIVATE_SESSION_'+str(self.turn),
            'citations':self.citations, 'sources':self.citations,
            'answer':'\n\n'.join(f'Zitat: "{c["text"]}"\nQuelle: {format_citation_source(c)}'
                                 for c in self.citations)}

    def run_check(self):
        return run_reference_check('rev', self.dataset, self.chunks, self.request)

    def test_fresh_sessions_and_no_identifiers_in_report(self):
        report = self.run_check()
        self.assertTrue(report['passed'])
        self.assertEqual([c[2] for c in self.calls if c[0] == '/chat'], [None, None])
        self.assertNotIn('PRIVATE_SESSION', json.dumps(report))

    def test_comparison_requires_both_references(self):
        self.answers[1] = [self.chunks[1]]
        report = self.run_check()
        self.assertFalse(report['passed'])
        self.assertFalse(report['cases'][1]['checks']['reference_found'])
        self.assertTrue(report['cases'][1]['checks']['citations_valid'])

    def test_complete_alternative_evidence_set_is_accepted(self):
        self.dataset['cases'][1]['evidence_sets'].append([self.chunks[0]])
        self.answers[1] = [self.chunks[0]]
        self.assertTrue(self.run_check()['passed'])

    def test_invalid_annotations_stop_before_requests(self):
        bad = copy.deepcopy(self.dataset)
        bad['cases'][1]['evidence_sets'][0][0]['text'] = 'Invented'
        with self.assertRaises(ValueError):
            run_reference_check('rev', bad, self.chunks, self.request)
        self.assertEqual(self.calls, [])

    def test_revision_mismatch_stops_before_chat(self):
        report = run_reference_check('other', self.dataset, self.chunks, self.request)
        self.assertFalse(report['passed'])
        self.assertEqual(len(self.calls), 1)

    def test_changed_deployment_invalidates_result(self):
        self.after = 'changed'
        self.assertEqual(self.run_check()['failure'], 'deployment_changed_during_run')

    def test_errors_are_not_retried_or_exposed(self):
        calls = []
        def broken(path, *args, **kwargs):
            calls.append(path)
            if path == '/health':
                return {'status':'ok', 'revision':'rev'}
            raise RuntimeError('PRIVATE_ERROR')
        report = run_reference_check('rev', self.dataset, self.chunks, broken)
        self.assertEqual(calls, ['/health', '/chat'])
        self.assertNotIn('PRIVATE_ERROR', json.dumps(report))
        self.assertFalse(report['passed'])

    def test_modified_quote_fails_despite_correct_reference(self):
        self.answers[0] = [dict(self.chunks[0], text='Invented answer')]
        report = self.run_check()
        self.assertTrue(report['cases'][0]['checks']['reference_found'])
        self.assertFalse(report['cases'][0]['checks']['citations_valid'])
        self.assertFalse(report['passed'])

    def test_sources_mismatch_fails(self):
        def wrong_sources(path, *args, **kwargs):
            if path == '/sources':
                return []
            return self.request(path, *args, **kwargs)
        report = run_reference_check('rev', self.dataset, self.chunks, wrong_sources)
        self.assertFalse(report['passed'])
        self.assertFalse(report['cases'][0]['checks']['sources_match'])
