import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from evaluation.passage_selection import build_passages, validate_passage_ids, select_passages
from test_context_windows import segment


class PassageTests(unittest.TestCase):
    def test_offsets_preserve_original_characters_and_decimal_numbers(self):
        original = '  Bei 3.5 Volt gilt A.\n\nDanach gilt B! Ohne Satzende  '
        candidates = [dict(segment(0, text=original))]
        passages = build_passages(candidates)
        self.assertEqual([p['text'] for p in passages],
                         ['Bei 3.5 Volt gilt A.', 'Danach gilt B!', 'Ohne Satzende'])
        for p in passages:
            self.assertEqual(p['text'], original[p['start']:p['end']])
        self.assertEqual([p['id'] for p in passages], ['Q1-P1','Q1-P2','Q1-P3'])

    def test_empty_segments_and_duplicate_text_have_unambiguous_ids(self):
        passages = build_passages([{'text':' '},{'text':'Identisch. Identisch.'}])
        self.assertEqual([p['id'] for p in passages], ['Q2-P1','Q2-P2'])
        self.assertNotEqual(passages[0]['start'],passages[1]['start'])

    def test_bad_id_rejects_entire_selection(self):
        passages = build_passages([{'text':'Original.'}])
        for raw in ['{"selected":["Q1-P1","Q9-P1"]}', '{"selected":[true]}',
                    '{"selected":["Original."]}', '{"selected":[1]}']:
            self.assertEqual(validate_passage_ids(raw, passages, 'Question')[0], [])

    def test_original_order_and_deduplication(self):
        passages = build_passages([{'text':'A. B.'}])
        chosen,status=validate_passage_ids('{"selected":["Q1-P2","Q1-P1","Q1-P2"]}',passages,'Question')
        self.assertEqual(status,'accepted')
        self.assertEqual(chosen,passages)

    def test_numeric_guard_uses_only_selected_passages(self):
        passages=build_passages([{'text':'Eine Spannung. Sie beträgt 12 Volt.'}])
        self.assertEqual(validate_passage_ids('{"selected":["Q1-P1"]}',passages,
            'Wie groß ist die Spannung?')[1],'quantity_not_supported')
        self.assertEqual(validate_passage_ids('{"selected":["Q1-P2"]}',passages,
            'Wie groß ist die Spannung?')[1],'accepted')

    def test_context_and_metadata_remain_available_but_output_is_exact_passage(self):
        candidates=[dict(segment(0,text='Bedingung. Ergebnis.'))]
        rag=SimpleNamespace(chat_model='test',trace_sources=Mock(),_chat_completion=Mock(
            return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"selected":["Q1-P2"]}'))])))
        sources,quotes=select_passages(rag,'Question',candidates)
        self.assertEqual(sources,[1])
        self.assertEqual(quotes[0]['text'],'Ergebnis.')
        self.assertEqual(quotes[0]['time_range'],candidates[0]['time_range'])
        prompt=json.loads(rag._chat_completion.call_args.kwargs['messages'][1]['content'])
        self.assertEqual([p['text'] for p in prompt['sources'][0]['passages']],['Bedingung.','Ergebnis.'])
        self.assertEqual(quotes[0]['citation']['time_range'],candidates[0]['time_range'])
