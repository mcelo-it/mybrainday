import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from backend.conversation import ConversationState
from backend.index_manifest import CacheValidationError
from backend.rag_utils import RAGSystem


class IndexManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.rag = RAGSystem.__new__(RAGSystem)
        r = self.rag
        r.state = ConversationState()
        r.docs_path = root / "docs"
        r.docs_path.mkdir()
        self.source = r.docs_path / "01 Test 1 Grundlagen.txt"
        self.source.write_text("(0:00:00 - 0:00:10)\nOriginaltext\n", encoding="utf-8")
        r.cache_dir = root / "cache"
        r.chunks_file = r.cache_dir / "chunks.json"
        r.embeddings_file = r.cache_dir / "embeddings.npy"
        r.meta_file = r.cache_dir / "meta.json"
        r.max_files = r.max_chunks = None
        r.embedding_model = "test-model"
        r.chat_model = "test-chat"
        r.retrieval_top_k = 8
        r.min_similarity_score = .3
        r.retrieval_mode = "semantic"
        with contextlib.redirect_stdout(io.StringIO()):
            r.load_documents()
            r.build_chunks()
        r.embeddings = np.array([[1., 0.]], dtype=np.float32)

    def save(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.rag.save_cache()

    def load(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.rag.load_cache()

    def test_roundtrip_and_chat_settings_do_not_invalidate_embeddings(self):
        self.save()
        expected = self.rag.index_status.copy()
        self.rag.chat_model = "different-chat"
        self.rag.retrieval_top_k = 4
        self.load()
        self.assertEqual(self.rag.index_status, expected)

    def test_same_shape_vector_corruption_is_rejected_without_replacing_loaded_data(self):
        self.save()
        before = self.rag.embeddings
        np.save(self.rag.embeddings_file, np.array([[0., 1.]], dtype=np.float32))
        with self.assertRaises(CacheValidationError):
            self.load()
        self.assertIs(self.rag.embeddings, before)

    def test_changed_transcript_or_model_is_rejected(self):
        self.save()
        self.rag.embedding_model = "other"
        with self.assertRaises(CacheValidationError):
            self.load()
        self.rag.embedding_model = "test-model"
        self.source.write_text("(0:00:00 - 0:00:10)\nAnderer Text", encoding="utf-8")
        with self.assertRaises(CacheValidationError):
            self.load()

    def test_legacy_remains_explicitly_unverified(self):
        self.save()
        meta = json.loads(self.rag.meta_file.read_text())
        del meta["index_manifest"]
        self.rag.meta_file.write_text(json.dumps(meta))
        with self.assertWarns(RuntimeWarning):
            self.load()
        self.assertEqual(self.rag.index_status["index_validation"], "legacy-structural-only")
        self.assertNotIn("index_manifest", json.loads(self.rag.meta_file.read_text()))

    def test_missing_and_partial_cache_are_distinct(self):
        with self.assertRaises(FileNotFoundError):
            self.load()
        self.save()
        self.rag.embeddings_file.unlink()
        with self.assertRaises(CacheValidationError):
            self.load()

    def test_interrupted_write_cannot_be_loaded_as_valid_cache(self):
        self.save()
        with patch("backend.rag_utils.np.save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.save()
        self.assertEqual(json.loads(self.rag.meta_file.read_text())["index_manifest"]["state"], "incomplete")
        with self.assertRaises(CacheValidationError):
            self.load()

    def test_changed_chunks_and_nonfinite_vectors_are_rejected(self):
        self.save()
        chunks = json.loads(self.rag.chunks_file.read_text())
        chunks[0]["time_range"] = "(0:01:00 - 0:01:10)"
        self.rag.chunks_file.write_text(json.dumps(chunks))
        with self.assertRaises(CacheValidationError):
            self.load()
        self.save()
        np.save(self.rag.embeddings_file, np.array([[float('nan'), 0.]], dtype=np.float32))
        with self.assertRaises(CacheValidationError):
            self.load()


if __name__ == "__main__":
    unittest.main()
