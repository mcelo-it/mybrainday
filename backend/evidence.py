"""Validate extractive review evidence; conservative, not semantic entailment."""
import json
import re


def quantity_supported(query, spans):
    # Follow-up search wrappers preserve the actual current question last.
    query = re.split(r'Originale Folgefrage:|Folgefrage:', query)[-1].casefold()
    if not re.search(r'wie\s+(?:viel|groß|gross|hoch|stark)|welch\w*\s+(?:wert|spannung|stromstärke)', query):
        return True
    text = ' '.join(spans).casefold()
    number = r'(?:[+-]?\d+(?:[.,]\d+)?|null|ein(?:s|e|en)?|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn)'
    # A dimensional unit must occur with a value, not just in an acronym/name.
    if 'spannung' in query:
        return bool(re.search(number + r'\s*(?:[mkµu]?v\b|(?:milli|kilo|mega)?volt\b)', text)
                    or re.search(r'spannung\s+(?:ist\s+|beträgt\s+)?null\b', text))
    if 'strom' in query:
        return bool(re.search(number + r'\s*(?:[mkµu]?a\b|(?:milli|kilo|mikro)?ampere\b)', text)
                    or re.search(r'kein(?:en)?\s+strom\b|strom\s+(?:ist\s+|beträgt\s+)?null\b', text))
    return True  # Other dimensions rely on the model review, no fake coverage claim.


def validate_review(raw, candidates, query):
    """Return indices plus bounded diagnostics, never model text or excerpts."""
    diagnostics = {'status': 'invalid_json', 'proposed': [], 'whitespace_normalized': False}

    def finish(status, indices=None):
        diagnostics['status'] = status
        return indices or [], diagnostics

    try:
        result = json.loads(raw)
    except (ValueError, TypeError):
        return finish('invalid_json')
    if not isinstance(result, dict) or set(result) != {'selected', 'evidence'}:
        return finish('invalid_schema')
    selected, evidence = result['selected'], result['evidence']
    if not isinstance(selected, list) or not isinstance(evidence, list):
        return finish('invalid_schema')
    if any(type(i) is not int or not 1 <= i <= len(candidates) for i in selected):
        return finish('invalid_source')
    diagnostics['proposed'] = sorted(set(selected))[:40]
    if not selected and not evidence:
        return finish('model_abstained')
    if not selected or not evidence:
        return finish('missing_evidence')
    spans = []
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {'source', 'span'}:
            return finish('invalid_evidence_schema')
        source, span = item['source'], item['span']
        if type(source) is not int or source not in selected:
            return finish('invalid_evidence_source')
        if not isinstance(span, str) or not span.strip():
            return finish('empty_span')
        original = candidates[source - 1]['text']
        if span not in original:
            # Token sequences must remain identical: only whitespace runs vary.
            # Output still uses untouched original chunks, never these spans.
            normalized_span = ' '.join(span.split())
            normalized_original = ' '.join(original.split())
            if normalized_span not in normalized_original:
                return finish('span_not_in_source')
            diagnostics['whitespace_normalized'] = True
        spans.append(span)
    if not quantity_supported(query, spans):
        return finish('quantity_not_supported')
    return finish('accepted', sorted(set(selected)))


def reviewed_indices(raw, candidates, query):
    """Compatibility wrapper for callers needing only the accepted indices."""
    return validate_review(raw, candidates, query)[0]
