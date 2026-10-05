import unittest
import numpy as np
from backend.lexical import BM25Index, hybrid_indices, tokenize


class LexicalTests(unittest.TestCase):
    def test_umlauts_acronyms_and_numbers(self):
        self.assertEqual(tokenize("Übergang UOC 1000 W/m²"), tokenize("Uebergang uoc 1000 W/m2"))
        self.assertEqual(tokenize("VDE-AR-N 4110"), ["vde", "ar", "n", "4110"])

    def test_bm25_matches_formula_and_does_not_boost_repeated_query_words(self):
        index = BM25Index(["uoc uoc", "anderes thema", "uoc"])
        scores = index.scores("UOC")
        idf = np.log1p((3 - 2 + 0.5) / (2 + 0.5))
        expected = idf * 2 * 2.5 / (2 + 1.5 * (0.25 + 0.75 * 2 / (5/3)))
        self.assertAlmostEqual(scores[0], expected)
        self.assertEqual(scores[1], 0)
        np.testing.assert_array_equal(index.scores("uoc uoc"), scores)

    def test_unknown_terms_and_empty_documents(self):
        np.testing.assert_array_equal(BM25Index(["", "UOC"]).scores("unbekannt"), [0, 0])
        self.assertEqual(BM25Index([]).scores("UOC").size, 0)

    def test_fusion_can_promote_lexical_match_without_mixing_raw_scores(self):
        semantic = np.array([0.9, 0.8, 0.6])
        lexical = np.array([0., 0., 10.])
        self.assertEqual(hybrid_indices(semantic, lexical, 1), [2])
        self.assertEqual(hybrid_indices(semantic, lexical * 100, 3), hybrid_indices(semantic, lexical, 3))
        np.testing.assert_array_equal(semantic, [0.9, 0.8, 0.6])

    def test_cosine_gate_cannot_be_bypassed_by_large_bm25(self):
        semantic = np.array([0.9, 0.29994, 0.29996])
        lexical = np.array([0., 10000., 1.])
        result = hybrid_indices(semantic, lexical, 3)
        self.assertNotIn(1, result)
        self.assertIn(2, result)

    def test_no_matching_terms_uses_semantic_order_without_zero_score_votes(self):
        self.assertEqual(hybrid_indices(np.array([0.8, 0.8, 0.1]), np.zeros(3), 8), [0, 1])

    def test_invalid_inputs(self):
        for semantic, lexical in [(np.array([0.5]), np.array([1., 2.])),
                                  (np.array([float('nan')]), np.array([1.]))]:
            with self.assertRaises(ValueError):
                hybrid_indices(semantic, lexical, 8)

    def test_reserved_lexical_candidate_survives_outside_semantic_window(self):
        semantic = np.linspace(.9, .4, 100)
        lexical = np.zeros(100)
        lexical[-1] = 10
        result = hybrid_indices(semantic, lexical, 8)
        self.assertIn(99, result)
        self.assertEqual(len(result), 8)
        self.assertEqual(hybrid_indices(semantic, lexical, 0), [])

    def test_question_words_do_not_outweigh_subject_and_negation_remains(self):
        index = BM25Index(['wie viel wie viel', 'leerlauf', 'nicht'])
        scores = index.scores('Wie viel Leerlauf nicht')
        self.assertEqual(scores[0], 0)
        self.assertGreater(scores[1], 0)
        self.assertGreater(scores[2], 0)


if __name__ == "__main__":
    unittest.main()
