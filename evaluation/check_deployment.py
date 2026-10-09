"""Manual deployment/dialog smoke test; uses the public service, not an API key."""
import argparse
import json
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen

from backend.citations import citation_from_chunk, format_citation_source

BASE_URL = 'https://mybrainday.onrender.com'
CASES = [
    ('pv-current', 'Wie viel Strom fließt beim Leerlauf eines PV-Moduls?',
     ('01 Stringdesign 2 Elektrische Kenngroessen.txt', '(0:02:02 - 0:02:16)')),
    ('pv-short-followup', 'Und wie groß ist die Spannung beim Kurzschluss?',
     ('01 Stringdesign 2 Elektrische Kenngroessen.txt', '(0:03:25 - 0:03:42)')),
    ('lwl-topic-change', 'Und welche Messverfahren werden bei der LWL-Prüfung eingesetzt?',
     ('26 LWL Pruefprotokolle 2 Normen.txt', '(0:03:40 - 0:03:48)')),
]


def request_json(path, message=None, token=None):
    headers = {'Accept': 'application/json'}
    data = None
    if message is not None:
        data = json.dumps({'message': message, 'include_diagnostics': True, 'include_evidence_debug': True}).encode()
        headers['Content-Type'] = 'application/json'
    if token:
        headers['X-Conversation-ID'] = token
    request = Request(BASE_URL + path, data=data, headers=headers)
    # No retries: a repeated POST could incur cost or mutate the dialogue twice.
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def check_answer(payload, expected, corpus):
    citations = payload.get('citations')
    if not isinstance(citations, list) or not citations:
        return {'citations_valid': False, 'reference_found': False, 'quote_only': False}
    valid, blocks, refs = True, [], set()
    for citation in citations:
        if not isinstance(citation, dict):
            valid = False
            continue
        key = (citation.get('filename'), citation.get('time_range'))
        original = corpus.get(key)
        if original is None:
            valid = False
            continue
        canonical = citation_from_chunk(original)
        valid &= all(citation.get(field) == value for field, value in canonical.items())
        blocks.append(f'Zitat: "{canonical["text"]}"\nQuelle: {format_citation_source(canonical)}')
        refs.add(key)
    reference_found = expected in refs if expected else all(
        isinstance(c, dict) and str(c.get('module_number', '')).lstrip('0') == '26'
        and str(c.get('subject_area_number')) == '4' for c in citations)
    checks = {'citations_valid': bool(valid), 'reference_found': reference_found,
              'quote_only': payload.get('answer') == '\n\n'.join(blocks)}
    if expected == CASES[2][2]:
        # Keep the previous topic-isolation requirement as a separate gate.
        checks['topic_scope_valid'] = all(
            isinstance(c, dict) and str(c.get('module_number', '')).lstrip('0') == '26'
            and str(c.get('subject_area_number')) == '4' for c in citations)
    return checks


def classify_outcome(payload, checks):
    """Describe the result without relaxing any pass/fail requirement."""
    if all(checks.values()):
        return 'reference_checks_passed'
    kind = (payload.get('diagnostics') or {}).get('answer_type')
    if payload.get('citations'):
        if not checks.get('citations_valid') or not checks.get('quote_only'):
            return 'invalid_quote_output'
        if not checks.get('sources_match') or not checks.get('response_sources_match'):
            return 'source_mismatch'
        return 'reference_not_confirmed'  # May be an alternative valid answer; review it.
    if kind == 'insufficient_evidence':
        return 'abstained'
    if kind == 'clarification':
        return 'clarification'
    return 'no_source_answer'


def reference_trace(diagnostics, expected):
    """Presence by actual stage, not a claim about semantic answer quality."""
    if not isinstance(diagnostics, dict) or not isinstance(diagnostics.get('trace'), list):
        return {'available': False}
    if expected is None:
        return {'available': True, 'stages': [], 'note': 'No exact reference for topic-change case'}
    stages = []
    for event in diagnostics['trace']:
        numbers = [source['number'] for source in event['sources']
                   if (source.get('filename'), source.get('time_range')) == expected]
        stage = {'stage': event['stage'], 'reference_present': bool(numbers),
                 'truncated': event['truncated']}
        if 'selected' in event:
            stage['reference_selected'] = any(n in event['selected'] for n in numbers)
        stages.append(stage)
    return {'available': True, 'stages': stages}


def run_check(expected_revision, chunks, request=request_json):
    corpus = {(c['filename'], c['time_range']): c for c in chunks}
    if len(corpus) != len(chunks) or any(ref not in corpus for _, _, ref in CASES if ref):
        raise ValueError('Local reference corpus is incomplete or ambiguous')
    report = {'expected_revision': expected_revision, 'passed': False, 'turns': []}
    try:
        before = request('/health')
        report['health_before'] = before
        if before.get('status') != 'ok' or before.get('revision') != expected_revision:
            report['failure'] = 'deployment_revision_mismatch_or_not_ready'
            return report
        token = None
        for case_id, question, expected in CASES:
            start = perf_counter()
            payload = request('/chat', question, token)
            elapsed = round((perf_counter() - start) * 1000)
            returned_token = payload.get('conversation_id')
            if not isinstance(returned_token, str) or not returned_token or (token and returned_token != token):
                report['failure'] = 'conversation_not_preserved'
                return report
            token = returned_token  # Never saved in report or printed.
            checks = check_answer(payload, expected, corpus)
            sources = request('/sources', token=token)
            checks['sources_match'] = sources == payload.get('citations')
            checks['response_sources_match'] = payload.get('sources') == payload.get('citations')
            report['turns'].append({'id': case_id, 'question': question,
                                   'answer': payload.get('answer'), 'citations': payload.get('citations'),
                                   'http_elapsed_ms': elapsed, 'checks': checks,
                                   'outcome': classify_outcome(payload, checks),
                                   'diagnostics': payload.get('diagnostics'),
                                   'reference_trace': reference_trace(payload.get('diagnostics'), expected),
                                   'passed': all(checks.values())})
        after = request('/health')
        report['health_after'] = after
        if after.get('revision') != expected_revision or after.get('status') != 'ok':
            report['failure'] = 'deployment_changed_during_run'
            return report
        report['passed'] = all(turn['passed'] for turn in report['turns'])
        if not report['passed']:
            report['failure'] = 'dialog_regression_checks_failed'
    except Exception as error:
        # No response bodies, headers, session tokens or provider errors in logs.
        report['failure'] = 'request_or_response_error'
        report['error_type'] = type(error).__name__
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-revision', required=True)
    parser.add_argument('--chunks', type=Path, default=Path('backend/cache/chunks.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    chunks = json.loads(args.chunks.read_text(encoding='utf-8'))
    report = run_check(args.expected_revision, chunks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'failure': report.get('failure'),
                      'turns_completed': len(report['turns']),
                      'expected_revision': report['expected_revision'],
                      'observed_revision': report.get('health_before', {}).get('revision'),
                      'turn_checks': [{'id': t['id'], 'outcome': t['outcome'], 'checks': t['checks'],
                                       'reference_trace': t['reference_trace']}
                                      for t in report['turns']]}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
