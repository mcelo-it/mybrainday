import json
import unittest

from backend.citations import citation_from_chunk, format_citation_source
from evaluation.check_deployment import CASES, check_answer, run_check


class DeploymentCheckTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [dict(filename=ref[0], time_range=ref[1], text='Original '+str(i),
                            module_number='01', module_name='Stringdesign', video_number='2',
                            video_name='Elektrische Kenngroessen')
                       for i, (_, _, ref) in enumerate(CASES[:2])]
        self.chunks.append(dict(filename=CASES[2][2][0], time_range=CASES[2][2][1],
                                text='Original LWL', module_number='26', module_name='LWL',
                                video_number='2', video_name='Normen'))
        self.calls, self.turn, self.health_count = [], 0, 0
        self.revision_after = 'revision'
        self.token = 'PRIVATE_SESSION'

    def request(self, path, message=None, token=None):
        self.calls.append((path, message, token))
        if path == '/health':
            self.health_count += 1
            return {'status': 'ok', 'revision': 'revision' if self.health_count == 1 else self.revision_after}
        if path == '/sources':
            return self.last_citations
        self.last_citations = [citation_from_chunk(self.chunks[self.turn])]
        self.turn += 1
        c = self.last_citations[0]
        return {'conversation_id': self.token, 'citations': self.last_citations,
                'sources': self.last_citations,
                'answer': f'Zitat: "{c["text"]}"\nQuelle: {format_citation_source(c)}'}

    def test_revision_mismatch_stops_before_paid_chat(self):
        report = run_check('other', self.chunks, self.request)
        self.assertFalse(report['passed'])
        self.assertEqual(len(self.calls), 1)

    def test_three_turns_preserve_session_and_redact_identifier(self):
        report = run_check('revision', self.chunks, self.request)
        self.assertTrue(report['passed'])
        chat_calls = [c for c in self.calls if c[0] == '/chat']
        self.assertEqual([c[2] for c in chat_calls], [None, self.token, self.token])
        self.assertNotIn(self.token, json.dumps(report))
        self.assertEqual(len(report['turns']), 3)

    def test_deployment_change_invalidates_run(self):
        self.revision_after = 'changed'
        report = run_check('revision', self.chunks, self.request)
        self.assertEqual(report['failure'], 'deployment_changed_during_run')
        self.assertFalse(report['passed'])

    def test_modified_quote_fails(self):
        payload = self.request('/chat')
        payload['citations'][0]['text'] = 'Invented value'
        corpus = {(c['filename'], c['time_range']): c for c in self.chunks}
        self.assertFalse(check_answer(payload, CASES[0][2], corpus)['citations_valid'])

    def test_request_error_not_retried_and_no_raw_error_saved(self):
        def broken(*args, **kwargs):
            raise RuntimeError('PRIVATE_ERROR')
        report = run_check('revision', self.chunks, broken)
        self.assertEqual(report['failure'], 'request_or_response_error')
        self.assertNotIn('PRIVATE_ERROR', json.dumps(report))

    def test_reference_presence_is_separate_from_exact_quote(self):
        payload = self.request('/chat')
        corpus = {(c['filename'], c['time_range']): c for c in self.chunks}
        result = check_answer(payload, CASES[1][2], corpus)
        self.assertTrue(result['citations_valid'])
        self.assertFalse(result['reference_found'])

    def test_lwl_topic_mention_without_method_reference_fails(self):
        self.turn = 2
        self.chunks[2]['time_range'] = '(0:00:00 - 0:00:10)'
        self.chunks[2]['text'] = 'Heute geht es um LWL-Prüfungen.'
        payload = self.request('/chat')
        corpus = {(c['filename'], c['time_range']): c for c in self.chunks}
        checks = check_answer(payload, CASES[2][2], corpus)
        self.assertTrue(checks['citations_valid'])
        self.assertTrue(checks['quote_only'])
        self.assertTrue(checks['topic_scope_valid'])
        self.assertFalse(checks['reference_found'])

    def test_lwl_reference_does_not_allow_previous_pv_topic_to_leak(self):
        self.turn = 2
        payload = self.request('/chat')
        pv = citation_from_chunk(self.chunks[0])
        payload['citations'].append(pv)
        payload['answer'] += f'\n\nZitat: "{pv["text"]}"\nQuelle: {format_citation_source(pv)}'
        corpus = {(c['filename'], c['time_range']): c for c in self.chunks}
        checks = check_answer(payload, CASES[2][2], corpus)
        self.assertTrue(checks['reference_found'])
        self.assertTrue(checks['citations_valid'])
        self.assertTrue(checks['quote_only'])
        self.assertFalse(checks['topic_scope_valid'])

    def test_missing_lwl_reference_stops_before_requests(self):
        with self.assertRaises(ValueError):
            run_check('revision', self.chunks[:2], self.request)
        self.assertEqual(self.calls, [])

    def test_sources_mismatch_fails(self):
        def wrong_sources(path, *args, **kwargs):
            if path == '/sources':
                return []
            return self.request(path, *args, **kwargs)
        report = run_check('revision', self.chunks, wrong_sources)
        self.assertFalse(report['passed'])
        self.assertFalse(report['turns'][0]['checks']['sources_match'])


if __name__ == '__main__':
    unittest.main()
