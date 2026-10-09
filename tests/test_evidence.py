import json
import unittest
from backend.evidence import reviewed_indices, quantity_supported, validate_review


class EvidenceTests(unittest.TestCase):
    def review(self, text, query, span=None):
        return reviewed_indices(json.dumps({'selected':[1], 'evidence':[{'source':1,'span':span or text}]}), [{'text':text}], query)

    def test_observed_topic_only_quote_is_rejected_for_both_dimensions(self):
        text = 'Wir haben Kurzschlussstrom und Leerlaufspannung vom Modul. Das ist die Kennlinie.'
        for query in ['Wie viel Strom fließt beim Leerlauf?', 'Wie groß ist die Spannung beim Kurzschluss?']:
            self.assertEqual(self.review(text, query), [])

    def test_literal_zero_and_units_are_accepted(self):
        self.assertEqual(self.review('Da ist er, null Ampere.', 'Wie viel Strom fließt?'), [1])
        self.assertEqual(self.review('Also haben wir an dem Punkt null Volt.', 'Wie groß ist die Spannung?'), [1])
        self.assertEqual(self.review('Es fließt kein Strom.', 'Wie viel Strom fließt?'), [1])
        self.assertEqual(self.review('Die Spannung beträgt 0,6 kV.', 'Wie hoch ist die Spannung?'), [1])

    def test_invented_or_cross_source_span_is_rejected(self):
        self.assertEqual(self.review('Kennlinie.', 'Wie groß ist die Spannung?', 'null Volt'), [])
        self.assertEqual(reviewed_indices('{"selected":[1],"evidence":[{"source":2,"span":"null Volt"}]}', [{'text':'A'},{'text':'null Volt'}], 'Spannung'), [])

    def test_wrong_dimension_is_rejected(self):
        self.assertEqual(self.review('null Ampere.', 'Wie groß ist die Spannung?'), [])

    def test_current_followup_determines_dimension(self):
        query = 'Vorherige Frage: Wie viel Strom?\nFolgefrage: Wie groß ist die Spannung?'
        self.assertFalse(quantity_supported(query, ['null Ampere']))
        self.assertTrue(quantity_supported(query, ['null Volt']))

    def test_invalid_schema_and_boolean_indices_are_rejected(self):
        for raw in ['1', 'NONE', '{"selected":[],"evidence":[]}', '{"selected":[true],"evidence":[]}']:
            self.assertEqual(reviewed_indices(raw, [{'text':'test'}], 'Frage'), [])

    def test_qualitative_question_accepts_exact_evidence(self):
        self.assertEqual(self.review('Plus und Minus sind getrennt.', 'Was bedeutet Leerlauf?'), [1])

    def test_whitespace_only_variation_is_accepted(self):
        self.assertEqual(self.review('Dämpfung. \n\nDann Durchgängigkeit.',
                                     'Welche Verfahren?', 'Dämpfung. Dann Durchgängigkeit.'), [1])

    def test_word_number_punctuation_and_omission_changes_stay_rejected(self):
        original = 'Die Spannung beträgt 12 Volt. Danach messen wir erneut.'
        for span in ['Die Spannung beträgt 24 Volt.', 'die Spannung beträgt 12 Volt.',
                     'Die Spannung beträgt 12 Volt!', '12Volt',
                     'Die Spannung beträgt 12 Volt. messen wir erneut.']:
            self.assertEqual(self.review(original, 'Welche Spannung?', span), [])

    def test_diagnostic_reasons_distinguish_abstention_from_validation(self):
        candidates = [{'text':'Dämpfung.\n\nDann Durchgängigkeit.'}]
        cases = [
            ('not JSON', 'invalid_json'),
            ('{}', 'invalid_schema'),
            ('{"selected":[],"evidence":[]}', 'model_abstained'),
            ('{"selected":[true],"evidence":[]}', 'invalid_source'),
            ('{"selected":[1],"evidence":[]}', 'missing_evidence'),
            ('{"selected":[1],"evidence":[{"source":1,"span":"PRIVATE invented"}]}', 'span_not_in_source'),
        ]
        for raw, expected in cases:
            indices, diagnostics = validate_review(raw, candidates, 'Welche Verfahren?')
            self.assertEqual(indices, [])
            self.assertEqual(diagnostics['status'], expected)
            self.assertNotIn('PRIVATE', str(diagnostics))
        raw = json.dumps({'selected':[1], 'evidence':[{'source':1,'span':'Dämpfung. Dann Durchgängigkeit.'}]})
        indices, diagnostics = validate_review(raw, candidates, 'Welche Verfahren?')
        self.assertEqual(indices, [1])
        self.assertEqual(diagnostics, {'status':'accepted', 'proposed':[1], 'whitespace_normalized':True})
