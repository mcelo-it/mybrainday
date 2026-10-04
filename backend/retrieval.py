"""Vectorized cosine retrieval; scores retain their original cosine meaning."""
import numpy as np


def embedding_norms(embeddings):
    if embeddings.ndim != 2 or not np.isfinite(embeddings).all():
        raise ValueError("Embeddings must be a finite two-dimensional matrix")
    return np.linalg.norm(embeddings, axis=1)


def cosine_scores(embeddings, query, norms=None):
    if query.ndim != 1 or embeddings.ndim != 2 or embeddings.shape[1] != query.size:
        raise ValueError("Query and embedding dimensions do not match")
    if not np.isfinite(query).all():
        raise ValueError("Query must contain finite values")
    if norms is None:
        norms = embedding_norms(embeddings)
    denominators = norms * np.linalg.norm(query)
    return np.divide(embeddings @ query, denominators,
                     out=np.zeros(len(embeddings), dtype=embeddings.dtype),
                     where=denominators != 0)


def ranked_indices(scores, top_k):
    if top_k < 0:
        raise ValueError("top_k must be non-negative")
    # Stable ordering preserves corpus order when scores are equal.
    return np.argsort(-scores, kind="stable")[:top_k]
