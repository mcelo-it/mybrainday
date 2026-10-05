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


def reviewed_indices(raw, candidates, query):
    try:
        result = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(result, dict) or set(result) != {'selected', 'evidence'}:
        return []
    selected, evidence = result['selected'], result['evidence']
    if not isinstance(selected, list) or not selected or not isinstance(evidence, list) or not evidence:
        return []
    if any(type(i) is not int or not 1 <= i <= len(candidates) for i in selected):
        return []
    spans = []
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {'source', 'span'}:
            return []
        source, span = item['source'], item['span']
        if type(source) is not int or source not in selected or not isinstance(span, str) or not span.strip():
            return []
        if span not in candidates[source - 1]['text']:
            return []
        spans.append(span)
    if not quantity_supported(query, spans):
        return []
    return sorted(set(selected))
