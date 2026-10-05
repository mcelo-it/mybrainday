"""Offline replay, or explicitly requested live retrieval against the full cache."""
import argparse
import hashlib
import json
from pathlib import Path

from backend.context_windows import expand_context


def key(chunk):
    return chunk["filename"], chunk["time_range"]


def corpus_digest(chunks):
    payload = json.dumps(chunks, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_dataset(dataset, chunks):
    corpus = {key(chunk): chunk for chunk in chunks}
    if len(corpus) != len(chunks):
        raise ValueError("Duplicate filename/timestamp pairs in corpus")
    ids = [case["id"] for case in dataset["cases"]]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Dataset needs nonempty, unique case IDs")
    for case in dataset["cases"]:
        if not case["evidence_sets"] or any(not group for group in case["evidence_sets"]):
            raise ValueError("Each case needs at least one nonempty evidence set")
        for group in case["evidence_sets"]:
            for evidence in group:
                actual = corpus.get(key(evidence))
                if actual is None or actual["text"].strip() != evidence["text"].strip():
                    raise ValueError(f"Missing or changed reference: {case['id']} {key(evidence)}")
    return corpus


def coverage(case, candidates):
    present = {key(chunk) for chunk in candidates}
    fractions = [sum(key(e) in present for e in group) / len(group)
                 for group in case["evidence_sets"]]
    return {"evidence_recall": max(fractions), "complete_evidence": max(fractions) == 1}


def evaluate(dataset, chunks, runs, top_k=8, min_score=0.30):
    corpus = validate_dataset(dataset, chunks)
    if set(runs) != {case["id"] for case in dataset["cases"]}:
        raise ValueError("Rankings must contain exactly the dataset case IDs")
    rows = []
    for case in dataset["cases"]:
        anchors = []
        for ref in runs[case["id"]][:top_k]:
            if key(ref) not in corpus:
                raise ValueError(f"Unknown retrieved source: {key(ref)}")
            score = float(ref["score"])
            if not -1 <= score <= 1:
                raise ValueError("Expected finite cosine similarity in [-1, 1]")
            anchors.append(dict(corpus[key(ref)], score=score))
        # The production relevance gate checks the highest-ranked seed.
        accepted = bool(anchors) and anchors[0]["score"] >= min_score
        context = expand_context(anchors, chunks) if accepted else []
        rows.append({"id": case["id"], "gate_passed": accepted,
                     "seeds": coverage(case, anchors), "context": coverage(case, context),
                     "context_chunks": len(context),
                     "context_chars": sum(len(c["text"]) for c in context)})
    return {"cases": rows, "summary": {
        stage: {metric: sum(row[stage][metric] for row in rows) / len(rows)
                for metric in ("evidence_recall", "complete_evidence")}
        for stage in ("seeds", "context")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/starter.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path("backend/cache"))
    parser.add_argument("--rankings", type=Path, help="Previously recorded rankings JSON")
    parser.add_argument("--live", action="store_true", help="Create paid query embeddings via OpenAI")
    parser.add_argument("--answers", action="store_true", help="Also run the full chatbot with paid chat calls; fresh session per question")
    parser.add_argument("--retrieval-mode", choices=["semantic", "hybrid"], default=None,
                        help="Live retrieval variant; defaults to semantic, independent of deployment environment")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--min-score", type=float, default=0.30)
    args = parser.parse_args()
    if args.live == bool(args.rankings):
        parser.error("Choose exactly one of --live or --rankings")
    if args.top_k < 1:
        parser.error("--top-k must be positive")
    if args.answers and not args.live:
        parser.error("--answers requires --live; recorded answers are replayed automatically")
    if args.retrieval_mode and not args.live:
        parser.error("Replay uses the recorded retrieval mode; omit --retrieval-mode")
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    chunks = json.loads((args.cache_dir / "chunks.json").read_text(encoding="utf-8"))
    validate_dataset(dataset, chunks)  # Fail before any paid requests.
    digest = corpus_digest(chunks)
    dataset_digest = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    responses = None
    if args.live:
        from backend.rag_utils import RAGSystem
        meta = json.loads((args.cache_dir / "meta.json").read_text(encoding="utf-8"))
        rag = RAGSystem(cache_dir=str(args.cache_dir.resolve()), embedding_model=meta["embedding_model"],
                        retrieval_top_k=args.top_k, min_similarity_score=args.min_score,
                        retrieval_mode=args.retrieval_mode or "semantic")
        # Explicit CLI path wins over deployment environment defaults.
        rag.cache_dir = args.cache_dir.resolve()
        rag.chunks_file = rag.cache_dir / "chunks.json"
        rag.embeddings_file = rag.cache_dir / "embeddings.npy"
        rag.load_cache()
        runs = {}
        if args.answers:
            from backend.conversation import ConversationState
            responses = {}
        for case in dataset["cases"]:
            if args.answers:
                worker = rag.for_conversation(ConversationState())
                answer = worker.ask(case["question"])
                retrieved = worker.state.last_retrieved_chunks
                responses[case["id"]] = {"answer": answer, "citations": worker.state.last_citations,
                                          "answer_type": worker.state.last_answer_type}
            else:
                retrieved = rag.retrieve(case["question"], args.top_k)
            runs[case["id"]] = [dict(filename=c["filename"], time_range=c["time_range"], score=c["score"])
                                for c in retrieved]
        provenance = {"corpus_sha256": digest, "dataset_sha256": dataset_digest,
                      "embedding_model": meta["embedding_model"], "top_k": args.top_k,
                      "chat_model": rag.chat_model if args.answers else None,
                      "retrieval_mode": args.retrieval_mode or "semantic",
                      "lexical_config": {"k1": 1.5, "b": 0.75, "rank_constant": 60, "rank_window": max(32, args.top_k)}
                          if args.retrieval_mode == "hybrid" else None,
                      "mode": "end_to_end" if args.answers else "retrieval"}
    else:
        recorded = json.loads(args.rankings.read_text(encoding="utf-8"))
        provenance, runs = recorded["provenance"], recorded["rankings"]
        responses = recorded.get("responses")
        if responses is not None and (recorded["parameters"]["top_k"] != args.top_k
                                       or recorded["parameters"]["min_score"] != args.min_score):
            raise ValueError("Answer replay requires the original top_k and min_score")
        if provenance["corpus_sha256"] != digest or provenance["dataset_sha256"] != dataset_digest:
            raise ValueError("Recorded corpus or dataset differs; cannot compare runs")
        if provenance["top_k"] < args.top_k:
            raise ValueError("Recorded rankings contain fewer requested ranks")
    report = evaluate(dataset, chunks, runs, args.top_k, args.min_score)
    if responses is not None:
        from .answers import attach_answers
        attach_answers(report, dataset, chunks, responses)
    report.update(provenance=provenance, rankings=runs,
                  parameters={"top_k": args.top_k, "min_score": args.min_score,
                              "before": 1, "after": 3, "max_chunks": 40, "max_chars": 60000})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
