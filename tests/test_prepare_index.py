import unittest
from unittest.mock import Mock

from backend.index_manifest import CacheValidationError
from backend.prepare_index import ensure_index


class PrepareIndexTests(unittest.TestCase):
    def test_valid_cache_is_reused_without_rebuild(self):
        rag = Mock()

        result = ensure_index(rag)

        self.assertEqual(result, "current")
        rag.load_documents.assert_called_once_with()
        rag.load_cache.assert_called_once_with()
        rag.build_chunks.assert_not_called()
        rag.create_embeddings.assert_not_called()
        rag.save_cache.assert_not_called()

    def test_stale_cache_is_rebuilt(self):
        rag = Mock()
        rag.load_cache.side_effect = CacheValidationError("stale")

        result = ensure_index(rag)

        self.assertEqual(result, "rebuilt")
        rag.load_documents.assert_called_once_with()
        rag.load_cache.assert_called_once_with()
        rag.build_chunks.assert_called_once_with()
        rag.create_embeddings.assert_called_once_with()
        rag.save_cache.assert_called_once_with()

    def test_missing_cache_is_rebuilt(self):
        rag = Mock()
        rag.load_cache.side_effect = FileNotFoundError("missing")

        result = ensure_index(rag)

        self.assertEqual(result, "rebuilt")
        rag.build_chunks.assert_called_once_with()
        rag.create_embeddings.assert_called_once_with()
        rag.save_cache.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
