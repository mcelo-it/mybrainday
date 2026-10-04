import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.citations import citation_from_chunk, format_citation_source
from evaluation.answers import evaluate_answer, attach_answers
from evaluation.check_ui_run import parse_answer
from evaluation.evaluate import main


class AnswerEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.chunk = dict(filename="01 Stringdesign 2 Elektrische Kenngroessen.txt",
                          module_number="01", module_name="Stringdesign", video_number="2",
                          video_name="Elektrische Kenngroessen", time_range="(0:02:02 - 0:02:16)",
                          text="Kein Strom. Null Ampere.")
        self.case = {"id": "q", "evidence_sets": [[self.chunk]]}
        self.citation = citation_from_chunk(self.chunk)
        self.answer = f'Zitat: "{self.citation["text"]}"\nQuelle: {format_citation_source(self.citation)}'

    def test_original_quote_with_metadata_counts(self):
        result = evaluate_answer(self.case, self.answer, [self.citation], [self.chunk])
        self.assertTrue(result["complete_evidence"])
        self.assertTrue(result["quote_only_format_matches"])

    def test_fabricated_text_with_real_timestamp_does_not_count(self):
        bad = dict(self.citation, text="Es fließen 12 Ampere.")
        result = evaluate_answer(self.case, self.answer, [bad], [self.chunk])
        self.assertFalse(result["complete_evidence"])
        self.assertEqual(result["citation_issues"][0]["fields"], ["text"])

    def test_wrong_subject_area_and_unknown_source_fail(self):
        for citation in [dict(self.citation, subject_area_name="Falsch"),
                         dict(self.citation, time_range="(1:00:00 - 1:00:10)")]:
            result = evaluate_answer(self.case, self.answer, [citation], [self.chunk])
            self.assertFalse(result["complete_evidence"])
            self.assertTrue(result["citation_issues"])

    def test_extra_generated_prose_is_detected(self):
        result = evaluate_answer(self.case, self.answer + "\nZusammenfassung", [self.citation], [self.chunk])
        self.assertFalse(result["quote_only_format_matches"])

    def test_diagnosis_distinguishes_missing_context_from_selection(self):
        for available in [False, True]:
            report = {"cases": [{"id": "q", "context": {"complete_evidence": available}}], "summary": {}}
            attach_answers(report, {"cases": [self.case]}, [self.chunk],
                           {"q": {"answer": "Kein Bestandteil der Lehrvideos", "citations": []}})
            diagnosis = report["cases"][0]["reference_diagnosis"]
            self.assertEqual(diagnosis, "reference_evidence_not_returned_despite_context" if available
                             else "reference_evidence_missing_from_context")

    def test_recorded_live_failure_is_not_mistaken_for_an_answer(self):
        root = Path(__file__).resolve().parents[1]
        dataset = json.loads((root / "evaluation/starter.json").read_text())
        capture = json.loads((root / "evaluation/results/live-ui-2026-10-04.json").read_text())
        case = next(c for c in dataset["cases"] if c["id"] == "pv-current")
        raw = next(r for r in capture["results"] if r["id"] == "pv-current")
        answer, citations = parse_answer(raw["chat"], case["question"])
        # The observed citation is a real quotation, but not the needed reference.
        actual = dict(citations[0])
        gold = dict(self.chunk, text=case["evidence_sets"][0][0]["text"])
        result = evaluate_answer(case, answer, citations, [actual, gold])
        self.assertEqual(result["verified_citation_count"], 1)
        self.assertEqual(result["evidence_recall"], 0)

    def test_full_run_uses_independent_states_and_replays_without_provider(self):
        states = []
        chunk, citation, answer = self.chunk, self.citation, self.answer

        class FakeRAG:
            chat_model = "mock-model"

            def __init__(self, **kwargs):
                pass

            def load_cache(self):
                pass

            def for_conversation(self, state):
                states.append(state)
                def ask(question):
                    state.last_retrieved_chunks = [dict(chunk, score=0.8)]
                    state.last_citations = [citation]
                    state.last_answer_type = "source_answer"
                    return answer
                return SimpleNamespace(state=state, ask=ask)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "chunks.json").write_text(json.dumps([dict(chunk, chunk_index=0)]))
            (root / "meta.json").write_text(json.dumps({"embedding_model": "mock-embedding"}))
            dataset = {"cases": [dict(self.case, id=id, question="Frage " + id) for id in ("a", "b")]}
            (root / "dataset.json").write_text(json.dumps(dataset))
            common = ["evaluate", "--cache-dir", str(root), "--dataset", str(root / "dataset.json")]
            args = common + ["--live", "--answers", "--output", str(root / "live.json")]
            with patch.dict(sys.modules, {"backend.rag_utils": SimpleNamespace(RAGSystem=FakeRAG)}):
                with patch.object(sys, "argv", args), contextlib.redirect_stdout(io.StringIO()):
                    main()
            self.assertEqual(len(states), 2)
            self.assertIsNot(states[0], states[1])
            args = common + ["--rankings", str(root / "live.json"), "--output", str(root / "replay.json")]
            with patch.object(sys, "argv", args), contextlib.redirect_stdout(io.StringIO()):
                main()
            live = json.loads((root / "live.json").read_text())
            replay = json.loads((root / "replay.json").read_text())
            self.assertEqual(live, replay)
            self.assertEqual(live["summary"]["answer"]["complete_evidence"], 1)


if __name__ == "__main__":
    unittest.main()
