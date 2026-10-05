"""Bounded chronological context from the same transcript, without re-embedding."""


def relevance_score(chunk):
    return max(chunk.get("score", 0.0), chunk.get("context_anchor_score", 0.0))


def expand_context(anchors, chunks, before=1, after=3, max_chunks=40, max_chars=60000):
    by_position = {
        (chunk.get("filename"), chunk.get("chunk_index")): chunk
        for chunk in chunks
        if chunk.get("filename") and isinstance(chunk.get("chunk_index"), int)
    }
    result, seen, chars = [], {}, 0
    def add(candidate, anchor, is_anchor):
        nonlocal chars
        filename, index = candidate.get("filename"), candidate.get("chunk_index")
        key = (filename, index) if isinstance(index, int) else (filename, candidate.get("time_range"), candidate.get("text"))
        score = relevance_score(anchor)
        if key in seen:
            seen[key]["context_anchor_score"] = max(seen[key].get("context_anchor_score", 0), score)
            return
        text = candidate.get("text", "")
        if len(result) >= max_chunks or chars + len(text) > max_chars:
            return
        item = dict(candidate)
        if not is_anchor:
            item.pop("score", None)
        item["context_anchor_score"] = score
        seen[key] = item
        result.append(item)
        chars += len(text)

    # Reserve every direct seed before neighbours can consume the shared budget.
    for anchor in anchors:
        add(anchor, anchor, True)
    for anchor in anchors:
        filename, position = anchor.get("filename"), anchor.get("chunk_index")
        if not filename or not isinstance(position, int):
            continue
        for index in range(max(0, position - before), position + after + 1):
            if index != position:
                candidate = by_position.get((filename, index))
                if candidate is not None:
                    add(candidate, anchor, False)
    # Keep each video's candidates in transcript order, even for overlapping windows.
    videos = list(dict.fromkeys(item.get("filename", "") for item in result))
    result.sort(key=lambda item: (videos.index(item.get("filename", "")), item.get("chunk_index", -1)))
    return result
