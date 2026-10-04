import unittest
import numpy as np
from backend.retrieval import cosine_scores, embedding_norms, ranked_indices


class RetrievalTests(unittest.TestCase):
    def test_vectorized_matches_scalar_cosine(self):
        rng = np.random.default_rng(12)
        vectors = rng.normal(size=(400, 64)).astype(np.float32)
        query = rng.normal(size=64).astype(np.float32)
        vectors[17] = 0
        expected = []
        for row in vectors:
            denominator = np.linalg.norm(row) * np.linalg.norm(query)
            expected.append(float(np.dot(row, query) / denominator) if denominator else 0)
        actual = cosine_scores(vectors, query, embedding_norms(vectors))
        np.testing.assert_allclose(actual, expected, atol=1e-7)
        np.testing.assert_array_equal(ranked_indices(actual, 8), np.argsort(-np.array(expected), kind="stable")[:8])

    def test_zero_query_ties_and_limits(self):
        scores = cosine_scores(np.eye(3, dtype=np.float32), np.zeros(3, dtype=np.float32))
        np.testing.assert_array_equal(ranked_indices(scores, 9), [0, 1, 2])
        self.assertEqual(len(ranked_indices(scores, 0)), 0)
        with self.assertRaises(ValueError):
            ranked_indices(scores, -1)

    def test_invalid_vectors(self):
        with self.assertRaises(ValueError):
            cosine_scores(np.eye(3), np.ones(2))
        with self.assertRaises(ValueError):
            embedding_norms(np.array([[float('nan')]]))


if __name__ == "__main__":
    unittest.main()
