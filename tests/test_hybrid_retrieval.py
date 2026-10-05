import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np

from backend.conversation import ConversationState
from backend.rag_utils import RAGSystem
from backend.retrieval import embedding_norms
from test_context_windows import segment


class HybridRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.rag = RAGSystem.__new__(RAGSystem)
        self.rag.state = ConversationState()
        self.rag.embeddings = np.array([[1, 0], [.8, .6], [.6, .8]], dtype=np.float32)
        self.rag._embedding_norms = embedding_norms(self.rag.embeddings)
        self.rag.chunks = [segment(i, text=text) for i, text in enumerate(["Kennlinie", "Strom", "UOC"])]
        self.rag.min_similarity_score = 0.3
        self.rag.retrieval_top_k = 1
        self.rag.embedding_model = "test"
        self.rag.client = Mock()
        self.rag.client.embeddings.create.return_value = SimpleNamespace(data=[SimpleNamespace(embedding=[1, 0])])

    def test_hybrid_promotes_match_but_returns_true_cosine_score(self):
        self.rag.retrieval_mode = "hybrid"
        self.rag.prepare_lexical_index()
        result = self.rag.retrieve("UOC")
        self.assertEqual(result[0]["text"], "UOC")
        self.assertEqual(result[0]["score"], 0.6)
        self.assertNotIn("score", self.rag.chunks[2])
        worker = self.rag.for_conversation(ConversationState())
        self.assertIs(worker._lexical_index, self.rag._lexical_index)
        self.assertIsNot(worker.state, self.rag.state)
        self.rag.client.embeddings.create.assert_called_once()

    def test_semantic_mode_keeps_previous_order_and_needs_no_lexical_index(self):
        self.rag.retrieval_mode = "semantic"
        self.rag.prepare_lexical_index()
        self.assertIsNone(self.rag._lexical_index)
        self.assertEqual(self.rag.retrieve("UOC")[0]["text"], "Kennlinie")

    def test_rebuilding_index_replaces_old_lexical_content(self):
        self.rag.retrieval_mode = "hybrid"
        self.rag.prepare_lexical_index()
        self.rag.chunks = [segment(0, text="NeuerBegriff")]
        self.rag.prepare_lexical_index()
        self.assertEqual(self.rag._lexical_index.size, 1)
        self.assertEqual(float(self.rag._lexical_index.scores("UOC")[0]), 0.)


if __name__ == "__main__":
    unittest.main()
