"""Validate extractive review evidence; conservative, not semantic entailment."""
import json
import re


_STOPWORDS = {
    'aber', 'als', 'auch', 'auf', 'aus', 'bei', 'das', 'dass', 'dem', 'den', 'der', 'des', 'die', 'ein',
    'eine', 'einer', 'eines', 'für', 'fuer', 'hat', 'haben', 'ist', 'im', 'in', 'mit', 'oder', 'sich',
    'sind', 'und', 'von', 'warum', 'was', 'welche', 'welcher', 'welches', 'wie', 'wird', 'zu', 'zur', 'zum'
}


def _content_terms(text):
    return {
        token for token in re.findall(r'[a-zA-ZäöüÄÖÜß0-9]+', text.casefold())
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _legacy_answer_relevance_order(query, selected, evidence, candidates):
    """Rank old-schema evidence by answer relevance, never by module/video/source order."""
    current_query = re.split(r'Originale Folgefrage:|Folgefrage:', query)[-1]
    query_terms = _content_terms(current_query)
    evidence_by_source = {}
    for item in evidence:
        if isinstance(item, dict) and isinstance(item.get('source'), int) and isinstance(item.get('span'), str):
            evidence_by_source.setdefault(item['source'], []).append(item['span'])

    def score(source):
        spans = evidence_by_source.get(source, [])
        evidence_text = ' '.join(spans)
        evidence_terms = _content_terms(evidence_text)
        overlap = len(query_terms & evidence_terms) / max(1, len(query_terms))
        candidate = candidates[source - 1]
        semantic = float(candidate.get('score', candidate.get('context_anchor_score', 0.0)) or 0.0)

        # Direct answer signals help result/value passages outrank nearby setup text.
        direct_signal = 0.0
        lowered_query = current_query.casefold()
        lowered_evidence = evidence_text.casefold()
        if re.search(r'wie\s+(?:viel|groß|gross|hoch|stark)|welch\w*\s+wert', lowered_query):
            if re.search(r'\b\d+(?:[.,]\d+)?\s*(?:[mkµu]?[va w]|volt|ampere|watt)\b', lowered_evidence):
                direct_signal += 1.0
            if re.search(r'\b(?:null|kein(?:en)?)\b', lowered_evidence):
                direct_signal += 0.8
        if any(term in lowered_evidence for term in ('beträgt', 'ist', 'ergibt', 'entspricht', 'bedeutet')):
            direct_signal += 0.2

        # Tuple comparison is deterministic and independent of transcript ordering.
        return (direct_signal, overlap, semantic)

    ranked = sorted(dict.fromkeys(selected), key=score, reverse=True)
    return ranked


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

    new_schema = set(result) == {'answer_sources', 'supporting_sources', 'evidence'}
    legacy_schema = set(result) == {'selected', 'evidence'}

    # New schema: answer sources are structurally separated from supporting
    # context so output order no longer depends on source/module/video order.
    if new_schema:
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
    elif legacy_schema:
        selected, evidence = result['selected'], result['evidence']
        if not isinstance(selected, list) or not isinstance(evidence, list):
            return finish('invalid_schema')
        if any(type(i) is not int or not 1 <= i <= len(candidates) for i in selected):
            return finish('invalid_source')
        if not selected and not evidence:
            return finish('model_abstained')
        if not selected or not evidence:
            return finish('missing_evidence')
        ordered = []  # assigned after evidence has been validated
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

    if legacy_schema:
        ordered = _legacy_answer_relevance_order(query, selected, evidence, candidates)

    return finish('accepted', ordered)


def reviewed_indices(raw, candidates, query):
    """Compatibility wrapper for callers needing only the accepted indices."""
    return validate_review(raw, candidates, query)[0]
