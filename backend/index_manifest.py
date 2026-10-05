"""Integrity checks for text-only embedding caches; legacy provenance stays explicit."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
import numpy as np


class CacheValidationError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def vector_digest(vectors):
    h = hashlib.sha256()
    h.update(digest({"shape": list(vectors.shape), "dtype": vectors.dtype.str}).encode())
    h.update(memoryview(np.ascontiguousarray(vectors)).cast("B"))
    return h.hexdigest()


def manifest(chunks, vectors, documents, model):
    source_hash = digest([{ "filename": d["filename"], "text": d["text"]}
                          for d in sorted(documents, key=lambda d: d["filename"])])
    record = {"format_version": 1, "state": "ready", "embedding_input": "transcript_text_v1",
              "embedding_model": model, "chunking_strategy": "timestamp_segments",
              "chunks_sha256": digest(chunks), "vectors_sha256": vector_digest(vectors),
              "sources_sha256": source_hash, "shape": list(vectors.shape), "dtype": vectors.dtype.str}
    record["index_id"] = digest(record)
    return record


def validate(meta, chunks, vectors, expected_chunks, documents, model):
    if vectors.ndim != 2 or vectors.shape[0] != len(chunks) or vectors.shape[1] == 0:
        raise CacheValidationError("Indexdimensionen passen nicht zu den Videoausschnitten.")
    if not np.issubdtype(vectors.dtype, np.floating) or not np.isfinite(vectors).all():
        raise CacheValidationError("Index enthält ungültige Embeddings.")
    if meta.get("embedding_model") != model or meta.get("chunking_strategy") != "timestamp_segments":
        raise CacheValidationError("Embedding-Modell oder Segmentierung des Index stimmt nicht überein.")
    if chunks != expected_chunks:
        raise CacheValidationError("Transkripte und gespeicherte Chunks unterscheiden sich. Kontrollierten Neuaufbau ausführen.")
    record = meta.get("index_manifest")
    if record is None:
        return {"index_id": "legacy-unverified", "index_validation": "legacy-structural-only"}
    actual = manifest(chunks, vectors, documents, model)
    if record != actual:
        raise CacheValidationError("Indexmanifest ist unvollständig, veraltet oder beschädigt. Kontrollierten Neuaufbau ausführen.")
    return {"index_id": actual["index_id"], "index_validation": "verified"}


def write_json_atomic(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
