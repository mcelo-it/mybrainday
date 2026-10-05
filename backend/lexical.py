"""Local BM25 and reciprocal-rank fusion; no network calls or new embeddings."""
from collections import Counter, defaultdict
import re
import unicodedata
import numpy as np

# Query-only function words; negations, numbers and technical terms remain.
QUERY_STOP_WORDS = set("wie viel gross groß hoch welche welcher welches welchen was ist sind sollte sollten wird werden der die das den dem des ein eine einer eines einem einen bei beim im in am an auf aus fuer für von vom zu zum zur und oder es sein".split())

# Keep predicates, but do not let their exact wording dominate the subject/state.
# This is an explicit heuristic, not POS tagging or a learned weighting scheme.
QUERY_TERM_WEIGHTS = dict.fromkeys(("fliesst", "fliessen", "betraegt", "betragen", "eingesetzt"), 0.25)


def tokenize(text):
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    # Preserve numbers/technical acronyms; no language model, stemming or guessed synonyms.
    return re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)


class BM25Index:
    def __init__(self, texts, k1=1.5, b=0.75):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("Invalid BM25 parameters")
        counters = [Counter(tokenize(text)) for text in texts]
        self.size = len(counters)
        lengths = np.array([sum(c.values()) for c in counters], dtype=float)
        average = float(lengths.mean()) if len(lengths) else 0.0
        self.norm = k1 * (1 - b + b * lengths / (average or 1.0))
        self.k1 = k1
        postings = defaultdict(list)
        for index, counts in enumerate(counters):
            for term, frequency in counts.items():
                postings[term].append((index, frequency))
        self.postings = {}
        for term, pairs in postings.items():
            indices, frequencies = zip(*pairs)
            df = len(pairs)
            self.postings[term] = (np.array(indices), np.array(frequencies, dtype=float),
                                  np.log1p((self.size - df + 0.5) / (df + 0.5)))

    def scores(self, query, use_predicate_weights=True):
        scores = np.zeros(self.size, dtype=float)
        for term in set(tokenize(query)) - QUERY_STOP_WORDS:
            posting = self.postings.get(term)
            if posting is not None:
                indices, frequencies, idf = posting
                weight = QUERY_TERM_WEIGHTS.get(term, 1.0) if use_predicate_weights else 1.0
                scores[indices] += weight * idf * frequencies * (self.k1 + 1) / (frequencies + self.norm[indices])
        return scores


def hybrid_indices(semantic_scores, lexical_scores, top_k, min_score=0.30, window=32, rank_constant=60):
    """Fuse ranks among cosine-qualified candidates; never reinterpret RRF as cosine."""
    if top_k < 0 or window < 1 or rank_constant < 1:
        raise ValueError("Invalid ranking parameters")
    if semantic_scores.shape != lexical_scores.shape or semantic_scores.ndim != 1:
        raise ValueError("Score arrays must have the same one-dimensional shape")
    if not np.isfinite(semantic_scores).all() or not np.isfinite(lexical_scores).all():
        raise ValueError("Scores must be finite")
    # Round just as production does before applying its relevance gate.
    eligible = np.array([round(float(score), 4) >= min_score for score in semantic_scores])
    width = max(window, top_k)
    semantic = [int(i) for i in np.argsort(-semantic_scores, kind="stable") if eligible[i]][:width]
    lexical = [int(i) for i in np.argsort(-lexical_scores, kind="stable")
               if eligible[i] and lexical_scores[i] > 0][:width]
    if not lexical:
        return semantic[:top_k]
    fused = defaultdict(float)
    for ranking in (semantic, lexical):
        for rank, index in enumerate(ranking, 1):
            fused[index] += 1.0 / (rank_constant + rank)
    ranking = sorted(fused, key=lambda i: (-fused[i], -float(semantic_scores[i]), i))
    # Preserve complementary lexical recall even outside the semantic rank window.
    # The final budget stays top_k and every reserved item still passes cosine.
    reserved = lexical[:min(len(lexical), max(1, top_k // 2))] if top_k else []
    chosen = set(reserved)
    for index in ranking:
        if len(chosen) >= top_k:
            break
        chosen.add(index)
    return [index for index in ranking if index in chosen]
