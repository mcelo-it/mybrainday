"""Compare lexical reference ranks on the full corpus without provider calls."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

from backend.citations import subject_area
from backend.lexical import BM25Index, QUERY_TERM_WEIGHTS
from evaluation.evaluate import validate_dataset


def compare(dataset, chunks):
    validate_dataset(dataset, chunks)
    lookup = {(c['filename'], c['time_range']): i for i, c in enumerate(chunks)}
    index = BM25Index([' '.join([subject_area(c['module_number'])['subject_area_name'],
                                c['module_name'], c['video_name'], c['text']]) for c in chunks])
    cases = []
    for case in dataset['cases']:
        row = {'id': case['id']}
        for label, weighted in [('baseline', False), ('weighted', True)]:
            scores = index.scores(case['question'], use_predicate_weights=weighted)
            order = np.argsort(-scores, kind='stable')
            ranks = np.empty(len(chunks), dtype=int)
            ranks[order] = np.arange(1, len(chunks) + 1)
            row[label] = [[int(ranks[lookup[(e['filename'], e['time_range'])]])
                           if scores[lookup[(e['filename'], e['time_range'])]] > 0 else None
                           for e in group] for group in case['evidence_sets']]
        cases.append(row)
    return {'mode': 'lexical_only_no_cosine_gate_or_model_calls', 'chunks': len(chunks),
            'query_term_weights': QUERY_TERM_WEIGHTS, 'cases': cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chunks', type=Path, default=Path('backend/cache/chunks.json'))
    parser.add_argument('--dataset', type=Path, default=Path('evaluation/starter.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = compare(json.loads(args.dataset.read_text(encoding='utf-8')), json.loads(args.chunks.read_text(encoding='utf-8')))
    report['corpus_file_sha256'] = hashlib.sha256(args.chunks.read_bytes()).hexdigest()
    report['dataset_file_sha256'] = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'chunks': report['chunks'], 'cases': len(report['cases'])}))


if __name__ == '__main__':
    main()
