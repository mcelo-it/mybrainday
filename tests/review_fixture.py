"""Add an explicit single-aspect mapping to legacy synthetic review fixtures."""
import json


def single_aspect_review(raw):
    try:
        result = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if isinstance(result, dict) and set(result) == {'selected', 'evidence'}:
        result['coverage'] = ([{'subject':'Test subject', 'property':'Test property',
                               'evidence':list(range(1, len(result['evidence']) + 1))}]
                              if result['selected'] else [])
        return json.dumps(result)
    return raw
