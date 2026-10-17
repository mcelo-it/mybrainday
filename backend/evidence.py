"""Validate extractive review evidence; conservative, not semantic entailment."""
import json
import re


def quantity_supported(query, spans):
    # Follow-up search wrappers preserve the actual current question last.
    query = re.split(r'Originale Folgefrage:|Folgefrage:', query)[-1].casefold()
    if not re.search(r'wie\s+(?:viel|groß|gross|hoch|stark)|welch\w*\s+(?:wert(?:e|en|es)?|spannung(?:en)?|stromstärke(?:n)?)\b', query):
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


def validate_review(raw, candidates, query, capture_mismatch=False):
    """Return indices and diagnostics; mismatch text requires explicit opt-in."""
    diagnostics = {'status': 'invalid_json', 'proposed': [], 'whitespace_normalized': False}

    def finish(status, indices=None):
        diagnostics['status'] = status
        return indices or [], diagnostics

    try:
        result = json.loads(raw)
    except (ValueError, TypeError):
        return finish('invalid_json')
    if not isinstance(result, dict):
        return finish('invalid_schema')

    # New schema: answer sources are structurally separated from supporting
    # context so output order no longer depends on source/module/video order.
    if set(result) == {'answer_sources', 'supporting_sources', 'evidence'}:
        answer_sources = result['answer_sources']
        supporting_sources = result['supporting_sources']
        evidence = result['evidence']
        if not isinstance(answer_sources, list) or not isinstance(supporting_sources, list) or not isinstance(evidence, list):
            return finish('invalid_schema')
        selected = list(dict.fromkeys(answer_sources + supporting_sources))
        if any(type(i) is not int or not 1 <= i <= len(candidates) for i in selected):
            return finish('invalid_source')
        if any(source in answer_sources for source in supporting_sources):
            return finish('invalid_schema')
        if not answer_sources and not supporting_sources and not evidence:
            return finish('model_abstained')
        if not answer_sources or not evidence:
            return finish('missing_evidence')
        ordered = list(dict.fromkeys(answer_sources)) + [
            source for source in supporting_sources if source not in answer_sources
        ]
    # Legacy schema is retained for tests/compatibility, but new review prompts
    # should no longer rely on list order to identify the actual answer.
    elif set(result) == {'selected', 'evidence'}:
        selected, evidence = result['selected'], result['evidence']
        if not isinstance(selected, list) or not isinstance(evidence, list):
            return finish('invalid_schema')
        if any(type(i) is not int or not 1 <= i <= len(candidates) for i in selected):
            return finish('invalid_source')
        if not selected and not evidence:
            return finish('model_abstained')
        if not selected or not evidence:
            return finish('missing_evidence')
        evidence_order = list(dict.fromkeys(
            item.get('source') for item in evidence if isinstance(item, dict)
        ))
        selected_order = list(dict.fromkeys(selected))
        ordered = evidence_order + [source for source in selected_order if source not in evidence_order]
    else:
        return finish('invalid_schema')

    diagnostics['proposed'] = list(dict.fromkeys(selected))[:40]
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
                if capture_mismatch:
                    chunk = candidates[source - 1]
                    diagnostics['mismatch'] = {
                        'source': source,
                        'filename': chunk.get('filename'),
                        'time_range': chunk.get('time_range'),
                        'model_span': span[:2000],
                        'original_text': original[:6000],
                        'model_span_truncated': len(span) > 2000,
                        'original_text_truncated': len(original) > 6000,
                        'matching_candidate_numbers': [i for i, c in enumerate(candidates[:40], 1)
                            if normalized_span in ' '.join(c['text'].split())],
                    }
                return finish('span_not_in_source')
            diagnostics['whitespace_normalized'] = True
        spans.append(span)
    if not quantity_supported(query, spans):
        return finish('quantity_not_supported')

    return finish('accepted', ordered)


def reviewed_indices(raw, candidates, query):
    """Compatibility wrapper for callers needing only the accepted indices."""
    return validate_review(raw, candidates, query)[0]
