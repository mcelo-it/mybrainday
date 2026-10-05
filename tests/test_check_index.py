import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from backend.check_index import main
from backend.rag_utils import RAGSystem


class CheckIndexTests(unittest.TestCase):
    def test_offline_constructor_does_not_create_provider_client(self):
        with patch("backend.rag_utils.OpenAI", side_effect=AssertionError("API client forbidden")):
            rag = RAGSystem(initialize_client=False)
        self.assertIsNone(rag.client)

    def test_missing_cache_is_failure_without_rebuild_or_client(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch("backend.rag_utils.OpenAI", side_effect=AssertionError("API client forbidden")), \
                 patch.object(RAGSystem, "create_embeddings", side_effect=AssertionError("No rebuild")), \
                 contextlib.redirect_stdout(output):
                code = main(["--cache-dir", directory, "--docs-dir", directory])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["result"], "failed")

    def test_success_prints_status_without_client(self):
        def load(rag):
            rag.index_status = {"index_id": "legacy-unverified", "index_validation": "legacy-structural-only"}
            rag.documents = [{}]
            rag.chunks = [{}, {}]
        output = io.StringIO()
        with patch("backend.rag_utils.OpenAI", side_effect=AssertionError("API client forbidden")), \
             patch.object(RAGSystem, "load_cache", load), contextlib.redirect_stdout(output):
            code = main([])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["chunks"], 2)


if __name__ == "__main__":
    unittest.main()
