"""Evaluate final quotations against the indexed originals, not just their IDs."""
from backend.citations import citation_from_chunk, format_citation_source
from .evaluate import coverage, key


def evaluate_answer(case, answer, citations, chunks):
    if not isinstance(answer, str) or not isinstance(citations, list):
        raise ValueError("Expected an answer string and a citations list")
    corpus = {key(chunk): chunk for chunk in chunks}
    verified, issues = [], []
    for index, citation in enumerate(citations):
        if not isinstance(citation, dict):
            issues.append({"index": index, "reason": "invalid_citation"})
            continue
        original = corpus.get((citation.get("filename"), citation.get("time_range")))
        if original is None:
            issues.append({"index": index, "reason": "unknown_source"})
            continue
        expected = citation_from_chunk(original)
        fields = [name for name in expected if name != "text_preview"]
        different = [name for name in fields if citation.get(name) != expected[name]]
        if different:
            issues.append({"index": index, "reason": "source_mismatch", "fields": different})
        else:
            verified.append(citation)
    # A generated value carrying a real timestamp must not count as evidence.
    result = coverage(case, verified)
    expected_answer = "\n\n".join(
        f'Zitat: "{c["text"]}"\nQuelle: {format_citation_source(c)}' for c in verified)
    result.update(citation_count=len(citations), verified_citation_count=len(verified),
                  citation_issues=issues,
                  quote_only_format_matches=(answer == expected_answer) if citations else None)
    return result


def attach_answers(report, dataset, chunks, responses):
    expected_ids = {case["id"] for case in dataset["cases"]}
    if set(responses) != expected_ids:
        raise ValueError("Responses must contain exactly the dataset case IDs")
    cases = {case["id"]: case for case in dataset["cases"]}
    for row in report["cases"]:
        response = responses[row["id"]]
        row["answer"] = evaluate_answer(cases[row["id"]], response["answer"], response["citations"], chunks)
        if row["answer"]["complete_evidence"]:
            diagnosis = "reference_evidence_returned"
        elif not row["context"]["complete_evidence"]:
            diagnosis = "reference_evidence_missing_from_context"
        else:
            diagnosis = "reference_evidence_not_returned_despite_context"
        # This identifies annotation coverage, not semantic correctness or causality.
        row["reference_diagnosis"] = diagnosis
    report["responses"] = responses
    report["summary"]["answer"] = {
        metric: sum(row["answer"][metric] for row in report["cases"]) / len(report["cases"])
        for metric in ("evidence_recall", "complete_evidence", "citation_count")}
