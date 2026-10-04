"""Check recorded visible UI answers and source dialogs against local transcripts."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from .answers import evaluate_answer


def read_chunks(docs_dir):
    chunks = []
    pattern = r"(\(\d{1,2}:\d{2}:\d{2}\s*-\s*\d{1,2}:\d{2}:\d{2}\))"
    for path in sorted(docs_dir.glob("*.txt")):
        meta = re.fullmatch(r"(\d+)\s+(.*?)\s+(\d+)\s+(.*)", path.stem)
        if not meta:
            continue
        parts = re.split(pattern, path.read_text(encoding="utf-8"))
        for index in range(1, len(parts) - 1, 2):
            chunks.append(dict(filename=path.name, chunk_index=(index-1)//2,
                               module_number=meta[1], module_name=meta[2],
                               video_number=meta[3], video_name=meta[4],
                               time_range=parts[index], text=parts[index+1].strip()))
    return chunks


def parse_answer(chat, question):
    if question not in chat:
        raise ValueError("Recorded question does not match dataset")
    answer = chat.split(question, 1)[1].strip()
    pattern = (r'Zitat: "(.*?)"\nQuelle: Fachbereich (\d+) - (.*?) \| '
               r'Modul (\d+) - (.*?) \| Video (\d+) - (.*?) \| '
               r'(\(\d+:\d+:\d+ - \d+:\d+:\d+\))')
    citations = []
    for match in re.finditer(pattern, answer, re.DOTALL):
        text, area_number, area, module_number, module, video_number, video, time = match.groups()
        citations.append(dict(text=text, subject_area_number=area_number, subject_area_name=area,
                              module_number=module_number, module_name=module,
                              video_number=video_number, video_name=video, time_range=time,
                              filename=f"{module_number} {module} {video_number} {video}.txt"))
    if 'Zitat:' in answer and not citations:
        raise ValueError("Unsupported visible citation format")
    return answer, citations


def check_ui_run(dataset, capture, chunks):
    cases = {case["id"]: case for case in dataset["cases"]}
    observed = [result["id"] for result in capture["results"]]
    if len(observed) != len(set(observed)) or set(observed) != set(cases):
        raise ValueError("Capture must contain every question exactly once")
    rows = []
    for result in capture["results"]:
        case = cases[result["id"]]
        answer, citations = parse_answer(result["chat"], case["question"])
        metrics = evaluate_answer(case, answer, citations, chunks)
        dialog = result["sources"]
        # Presence check, not proof that the dialog contains no extra cards.
        source_checks = [all(value in dialog for value in (
            c["text"], c["time_range"], f'Fachbereich {c["subject_area_number"]} · {c["subject_area_name"]}',
            f'Modul {c["module_number"]} · {c["module_name"]}', f'Video {c["video_number"]} · {c["video_name"]}'))
            for c in citations]
        rows.append(dict(id=case["id"], **metrics,
                         source_dialog_contains_all_citations=all(source_checks) if citations else None))
    return {"cases": rows, "summary": {
        "question_count": len(rows),
        "complete_reference_sets": sum(r["complete_evidence"] for r in rows),
        "citation_count": sum(r["citation_count"] for r in rows),
        "verified_citation_count": sum(r["verified_citation_count"] for r in rows),
        "quote_only_format_matches": sum(r["quote_only_format_matches"] is True for r in rows),
        "source_dialog_contains_all_citations": sum(r["source_dialog_contains_all_citations"] is True for r in rows)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/starter.json"))
    parser.add_argument("--docs-dir", type=Path, default=Path("backend/docs"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capture = json.loads(args.capture.read_text(encoding="utf-8"))
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    report = check_ui_run(dataset, capture, read_chunks(args.docs_dir))
    report["provenance"] = {"capture_sha256": hashlib.sha256(args.capture.read_bytes()).hexdigest(),
                            "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                            "observed_at": capture["observed_at"], "url": capture["url"],
                            "deployed_commit": None,
                            "note": "Visible UI evidence only; internal retrieval rankings unavailable"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
