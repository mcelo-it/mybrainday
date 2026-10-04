import copy
import unittest
from evaluation.evaluate import evaluate, validate_dataset


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [dict(filename="video.txt", chunk_index=i, time_range=str(i), text=text)
                       for i, text in enumerate(["Wir berechnen jetzt die Spannung.", "Bedingung", "Ergebnis"])]
        self.dataset = {"cases": [{"id": "q", "evidence_sets": [[self.chunks[1], self.chunks[2]]]}]}
        self.runs = {"q": [dict(filename="video.txt", time_range="0", score=0.6)]}

    def test_announcement_is_not_an_answer_but_neighbors_cover_evidence(self):
        result = evaluate(self.dataset, self.chunks, self.runs)["cases"][0]
        self.assertEqual(result["seeds"]["evidence_recall"], 0)
        self.assertFalse(result["seeds"]["complete_evidence"])
        self.assertTrue(result["context"]["complete_evidence"])

    def test_partial_evidence_does_not_count_as_complete(self):
        runs = {"q": [dict(filename="video.txt", time_range="1", score=0.6)]}
        result = evaluate(self.dataset, self.chunks, runs)["cases"][0]
        self.assertEqual(result["seeds"]["evidence_recall"], 0.5)
        self.assertFalse(result["seeds"]["complete_evidence"])

    def test_gate_blocks_expansion(self):
        self.runs["q"][0]["score"] = 0.29
        self.assertEqual(evaluate(self.dataset, self.chunks, self.runs)["cases"][0]["context_chunks"], 0)

    def test_stale_gold_and_missing_runs_fail(self):
        stale = copy.deepcopy(self.chunks)
        stale[1]["text"] = "changed"
        with self.assertRaises(ValueError):
            validate_dataset(self.dataset, stale)
        with self.assertRaises(ValueError):
            evaluate(self.dataset, self.chunks, {})


if __name__ == "__main__":
    unittest.main()
