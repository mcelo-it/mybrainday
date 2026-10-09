import copy
import json
import unittest
from backend.evidence import validate_review


class CoverageValidationTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [{'text':'Material A dehnt sich aus.'}, {'text':'Material B bleibt gleich.'}]
        self.raw = {'selected':[1,2], 'evidence':[
            {'source':1,'span':self.candidates[0]['text']},
            {'source':2,'span':self.candidates[1]['text']}], 'coverage':[
            {'subject':'Material A','property':'Temperaturverhalten','evidence':[1]},
            {'subject':'Material B','property':'Temperaturverhalten','evidence':[2]}]}
        self.query = 'Wie unterscheiden sich die Materialien bei Erwärmung?'

    def validate(self, raw=None):
        return validate_review(json.dumps(self.raw if raw is None else raw),
                               self.candidates, self.query, require_coverage=True)

    def test_two_sided_comparison_is_accepted(self):
        indices, diagnostic = self.validate()
        self.assertEqual(indices, [1,2])
        self.assertEqual(diagnostic['coverage_count'], 2)
        self.assertNotIn('Material', str(diagnostic))

    def test_missing_side_is_rejected_even_with_two_selected_sources(self):
        self.raw['coverage'].pop()
        self.assertEqual(self.validate()[1]['status'], 'incomplete_comparison_coverage')

    def test_uncovered_requirement_is_rejected(self):
        self.raw['coverage'][1]['evidence'] = []
        self.assertEqual(self.validate()[1]['status'], 'uncovered_requirement')

    def test_different_comparison_properties_are_rejected(self):
        self.raw['coverage'][1]['property'] = 'Farbe'
        self.assertEqual(self.validate()[1]['status'], 'incomplete_comparison_coverage')

    def test_invalid_evidence_links_are_rejected(self):
        for refs in [[3], [True], [0], ['1']]:
            self.raw['coverage'][1]['evidence'] = refs
            self.assertEqual(self.validate()[1]['status'], 'invalid_coverage_reference')

    def test_fabricated_evidence_is_still_rejected(self):
        self.raw['evidence'][1]['span'] = 'Material B dehnt sich aus.'
        self.assertEqual(self.validate()[1]['status'], 'span_not_in_source')

    def test_missing_mapping_rejected_and_explicit_abstention_accepted(self):
        raw = copy.deepcopy(self.raw)
        del raw['coverage']
        self.assertEqual(self.validate(raw)[1]['status'], 'invalid_schema')
        self.assertEqual(self.validate({'selected':[], 'evidence':[], 'coverage':[]})[1]['status'],
                         'model_abstained')

    def test_duplicate_subject_does_not_count_as_two_sides(self):
        self.raw['coverage'][1]['subject'] = ' material A '
        self.assertEqual(self.validate()[1]['status'], 'incomplete_comparison_coverage')
