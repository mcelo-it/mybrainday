"""Manual public-service check of the curated development reference set."""
import argparse
import json
from pathlib import Path
from time import perf_counter

from .check_deployment import request_json, check_answer, classify_outcome, reference_trace


def reference_key(chunk):
    return chunk['filename'], chunk['time_range']


def validate_dataset(dataset, chunks):
    corpus = {reference_key(c): c for c in chunks}
    cases = dataset['cases']
    if len(corpus) != len(chunks) or not 1 <= len(cases) <= 20:
        raise ValueError('Ambiguous corpus or invalid case count')
    ids = set()
    for case in cases:
        if not isinstance(case['id'], str) or not case['id'] or case['id'] in ids:
            raise ValueError('Invalid or duplicate case ID')
        ids.add(case['id'])
        if not isinstance(case['question'], str) or not case['question'].strip():
            raise ValueError('Empty question')
        if not case['evidence_sets'] or any(not group for group in case['evidence_sets']):
            raise ValueError('Missing reference evidence')
        for group in case['evidence_sets']:
            for ref in group:
                original = corpus.get(reference_key(ref))
                if original is None or original['text'].strip() != ref['text'].strip():
                    raise ValueError('Reference text missing or changed')
    return corpus


def run_reference_check(expected_revision, dataset, chunks, request=request_json):
    # Validate all annotations before any potentially paid requests.
    corpus = validate_dataset(dataset, chunks)
    report = {'expected_revision': expected_revision, 'dataset_status': dataset.get('status'),
              'passed': False, 'cases': []}
    try:
        before = request('/health')
        report['health_before'] = before
        if before.get('status') != 'ok' or before.get('revision') != expected_revision:
            report['failure'] = 'deployment_revision_mismatch_or_not_ready'
            return report
        for case in dataset['cases']:
            started = perf_counter()
            payload = request('/chat', case['question'], None)  # independent fresh session
            elapsed = round((perf_counter() - started) * 1000)
            token = payload.get('conversation_id')
            if not isinstance(token, str) or not token:
                report['failure'] = 'conversation_identifier_missing'
                return report
            groups = [[reference_key(ref) for ref in group] for group in case['evidence_sets']]
            checks = check_answer(payload, groups[0][0], corpus)
            citations = payload.get('citations')
            refs = {reference_key(c) for c in citations if isinstance(c, dict)
                    and 'filename' in c and 'time_range' in c} if isinstance(citations, list) else set()
            # All references in at least one acceptable evidence set are required.
            checks['reference_found'] = any(set(group) <= refs for group in groups)
            checks['sources_match'] = request('/sources', token=token) == citations
            checks['response_sources_match'] = payload.get('sources') == citations
            report['cases'].append({
                'id': case['id'], 'question': case['question'], 'answer': payload.get('answer'),
                'citations': citations, 'checks': checks, 'passed': all(checks.values()),
                'outcome': classify_outcome(payload, checks), 'http_elapsed_ms': elapsed,
                'diagnostics': payload.get('diagnostics'),
                'reference_traces': [dict(filename=f, time_range=t,
                    trace=reference_trace(payload.get('diagnostics'), (f, t)))
                    for f, t in sorted(set(ref for group in groups for ref in group))],
            })
        after = request('/health')
        report['health_after'] = after
        if after.get('status') != 'ok' or after.get('revision') != expected_revision:
            report['failure'] = 'deployment_changed_during_run'
            return report
        report['passed'] = all(case['passed'] for case in report['cases'])
        if not report['passed']:
            report['failure'] = 'reference_checks_failed'
    except Exception as error:
        report['failure'] = 'request_or_response_error'
        report['error_type'] = type(error).__name__
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-revision', required=True)
    parser.add_argument('--dataset', type=Path, default=Path('evaluation/starter.json'))
    parser.add_argument('--chunks', type=Path, default=Path('backend/cache/chunks.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_reference_check(args.expected_revision,
        json.loads(args.dataset.read_text(encoding='utf-8')),
        json.loads(args.chunks.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'failure': report.get('failure'),
        'expected_revision': report['expected_revision'],
        'observed_revision': report.get('health_before', {}).get('revision'),
        'cases_completed': len(report['cases']),
        'case_checks': [{k: row[k] for k in ('id', 'outcome', 'checks', 'reference_traces')}
                        for row in report['cases']]}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
