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
    for anchor in anchors:
        filename, position = anchor.get("filename"), anchor.get("chunk_index")
        if filename and isinstance(position, int):
            # Reserve the anchor before spending the remaining budget on neighbours.
            positions = [position] + [i for i in range(max(0, position - before), position + after + 1) if i != position]
            candidates = [(i, anchor if i == position else by_position.get((filename, i))) for i in positions]
        else:
            candidates = [(None, anchor)]
        group = []
        for index, candidate in candidates:
            if candidate is None:
                continue
            key = (filename, index) if index is not None else (filename, candidate.get("time_range"), candidate.get("text"))
            score = relevance_score(anchor)
            if key in seen:
                seen[key]["context_anchor_score"] = max(seen[key].get("context_anchor_score", 0), score)
                continue
            text = candidate.get("text", "")
            if len(result) + len(group) >= max_chunks or chars + len(text) > max_chars:
                continue
            item = dict(candidate)
            if candidate is not anchor:
                # A neighbour has no query similarity of its own in this retrieval.
                item.pop("score", None)
            item["context_anchor_score"] = score
            seen[key] = item
            group.append(item)
            chars += len(text)
        group.sort(key=lambda item: item.get("chunk_index", -1))
        result.extend(group)
    # Keep each video's candidates in transcript order, even for overlapping windows.
    videos = list(dict.fromkeys(item.get("filename", "") for item in result))
    result.sort(key=lambda item: (videos.index(item.get("filename", "")), item.get("chunk_index", -1)))
    return result
