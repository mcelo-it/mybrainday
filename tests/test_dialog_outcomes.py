import unittest
from evaluation.check_deployment import classify_outcome


class OutcomeTests(unittest.TestCase):
    def test_reference_checks_pass(self):
        self.assertEqual(classify_outcome({}, {'reference_found':True}), 'reference_checks_passed')

    def test_abstention_and_clarification_are_distinct_failures(self):
        checks = {'reference_found':False, 'citations_valid':False}
        for kind, expected in [('insufficient_evidence','abstained'), ('clarification','clarification')]:
            payload = {'citations':[], 'diagnostics':{'answer_type':kind}}
            self.assertEqual(classify_outcome(payload, checks), expected)
            self.assertFalse(all(checks.values()))

    def test_other_original_quote_is_unconfirmed_not_automatically_false(self):
        checks = dict(citations_valid=True, reference_found=False, quote_only=True,
                      sources_match=True, response_sources_match=True)
        self.assertEqual(classify_outcome({'citations':[{}]}, checks), 'reference_not_confirmed')

    def test_modified_quote_and_source_mismatch_are_separate(self):
        payload = {'citations':[{}]}
        checks = dict(citations_valid=False, reference_found=True, quote_only=True,
                      sources_match=True, response_sources_match=True)
        self.assertEqual(classify_outcome(payload, checks), 'invalid_quote_output')
        checks.update(citations_valid=True, sources_match=False)
        self.assertEqual(classify_outcome(payload, checks), 'source_mismatch')


if __name__ == '__main__':
    unittest.main()
