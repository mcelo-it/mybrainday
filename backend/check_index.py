"""Read-only cache validation without initializing an API client."""
import argparse
import contextlib
import io
import json
from pathlib import Path

from .rag_utils import RAGSystem


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, default=Path("backend/docs"))
    parser.add_argument("--cache-dir", type=Path, default=Path("backend/cache"))
    args = parser.parse_args(argv)
    try:
        rag = RAGSystem(initialize_client=False, retrieval_mode="semantic")
        # Explicit paths, independent of deployment environment defaults.
        rag.docs_path = args.docs_dir.resolve()
        rag.cache_dir = args.cache_dir.resolve()
        rag.chunks_file = rag.cache_dir / "chunks.json"
        rag.embeddings_file = rag.cache_dir / "embeddings.npy"
        rag.meta_file = rag.cache_dir / "meta.json"
        with contextlib.redirect_stdout(io.StringIO()):
            rag.load_cache()  # Never initialize_rag: no automatic rebuild on absence.
        result = {"result": "ok", **rag.index_status,
                  "documents": len(rag.documents), "chunks": len(rag.chunks)}
        code = 0
    except (OSError, ValueError) as error:
        result = {"result": "failed", "error": str(error)}
        code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
