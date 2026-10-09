"""Isolated live-model experiment on fixed candidate sets; never calls Render."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

from backend.conversation import ConversationState
from backend.rag_utils import RAGSystem
from .answers import evaluate_answer
from .evaluate import key, validate_dataset, corpus_digest

VARIANTS = ('selection_then_review', 'direct_review')


def prepare_cases(dataset, chunks, report, source_revision):
    corpus = validate_dataset(dataset, chunks)
    if any(report.get(field, {}).get('revision') != source_revision
           for field in ('health_before', 'health_after')) or report.get('expected_revision') != source_revision:
        raise ValueError('Source report revision is not confirmed')
    rows = report.get('cases', [])
    by_id = {r['id']: r for r in rows}
    if len(rows) != len(by_id) or set(by_id) != {c['id'] for c in dataset['cases']}:
        raise ValueError('Report must contain exactly the development case IDs')
    prepared = []
    for case in dataset['cases']:
        row = by_id[case['id']]
        if row.get('question') != case['question']:
            raise ValueError('Question changed since source run')
        events = [e for e in (row.get('diagnostics') or {}).get('trace', []) if e['stage'] == 'selection']
        if len(events) != 1 or events[0].get('truncated') is not False:
            raise ValueError('Expected one complete independent-question candidate set')
        refs = events[0]['sources']
        if not 1 <= len(refs) <= 40 or [r['number'] for r in refs] != list(range(1, len(refs)+1)):
            raise ValueError('Invalid candidate numbering')
        candidates = []
        for ref in refs:
            if key(ref) not in corpus:
                raise ValueError('Candidate missing from source revision corpus')
            candidate = dict(corpus[key(ref)])
            for field in ('score', 'context_anchor_score'):
                if field in ref:
                    candidate[field] = ref[field]
            candidates.append(candidate)
        if len({key(c) for c in candidates}) != len(candidates):
            raise ValueError('Duplicate candidates')
        prepared.append((case, candidates))
    return prepared


def make_rag(client):
    # No index initialization, retrieval, embeddings or production sessions.
    rag = RAGSystem.__new__(RAGSystem)
    rag.client = client
    rag.chat_model = 'gpt-4.1-mini'
    rag.state = ConversationState(diagnostics_enabled=True, evidence_debug_enabled=True)
    return rag


def run_replay(prepared, chunks, rag_factory):
    result = {'completed': False, 'results': []}
    try:
        for index, (case, candidates) in enumerate(prepared):
            # Alternate order to reduce systematic time/order effects.
            variants = VARIANTS if index % 2 == 0 else VARIANTS[::-1]
            for variant in variants:
                rag = rag_factory()
                supplied = [dict(c) for c in candidates]
                start = perf_counter()
                if variant == 'selection_then_review':
                    ids = rag.select_relevant_quotes(case['question'], supplied)
                else:
                    ids = rag.review_quote_sufficiency(case['question'], supplied, [])
                selected = [supplied[i-1] for i in ids]
                answer = rag.construct_answer_from_chunks(selected) if selected else ''
                evaluation = evaluate_answer(case, answer, rag.state.last_citations, chunks)
                result['results'].append({
                    'id': case['id'], 'variant': variant, 'selected': ids,
                    'candidate_sha256': hashlib.sha256(json.dumps(candidates,
                        ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                    'answer': answer, 'citations': rag.state.last_citations,
                    'evaluation': evaluation, 'trace': rag.state.last_trace,
                    'metrics': rag.state.last_metrics,
                    'elapsed_ms': round((perf_counter()-start)*1000),
                })
        result['completed'] = True
    except Exception as error:
        result['failure'] = 'experiment_error'
        result['error_type'] = type(error).__name__  # No raw provider errors/secrets.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--chunks', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, default=Path('evaluation/starter.json'))
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'completed': False, 'results': []}
    try:
        dataset = json.loads(args.dataset.read_text(encoding='utf-8'))
        chunks = json.loads(args.chunks.read_text(encoding='utf-8'))
        report = json.loads(args.report.read_text(encoding='utf-8'))
        prepared = prepare_cases(dataset, chunks, report, args.source_revision)
        if not os.environ.get('OPENAI_API_KEY'):
            raise ValueError('OPENAI_API_KEY is required')
        from openai import OpenAI
        client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], max_retries=0, timeout=90)
        result = run_replay(prepared, chunks, lambda: make_rag(client))
        result.update(source_revision=args.source_revision, corpus_sha256=corpus_digest(chunks),
                      experiment_revision=os.environ.get('GITHUB_SHA'), model='gpt-4.1-mini',
                      dataset_status=dataset.get('status'), repeats=1)
    except Exception as error:
        result.update(failure='preflight_or_setup_error', error_type=type(error).__name__)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'completed': result['completed'], 'failure':result.get('failure'),
        'results': [{'id':r['id'], 'variant':r['variant'],
                     'complete_evidence':r['evaluation']['complete_evidence'],
                     'evidence_recall':r['evaluation']['evidence_recall'],
                     'model_calls':r['metrics'].get('model_calls')}
                    for r in result['results']]}))
    # Failed reference coverage is an experimental result, not a workflow failure.
    raise SystemExit(0 if result['completed'] else 1)


if __name__ == '__main__':
    main()
