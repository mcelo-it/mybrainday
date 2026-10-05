"""Per-turn model usage; never stores prompts, quotations, identifiers or errors."""
from time import perf_counter


def measured_call(metrics, stage, kind, operation, **kwargs):
    start = perf_counter()
    response, succeeded = None, False
    try:
        response = operation(**kwargs)
        succeeded = True
        return response
    finally:
        usage = getattr(response, "usage", None)
        record = {"stage": stage, "kind": kind, "model": kwargs.get("model"),
                  "elapsed_ms": round((perf_counter() - start) * 1000, 3), "success": succeeded}
        for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = getattr(usage, name, None)
            record[name] = value if type(value) is int and value >= 0 else None
        metrics["model_calls"] = metrics.get("model_calls", 0) + 1
        metrics["failed_calls"] = metrics.get("failed_calls", 0) + int(not succeeded)
        metrics["usage_missing_calls"] = metrics.get("usage_missing_calls", 0) + int(record["total_tokens"] is None)
        for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            key = "reported_" + name
            metrics[key] = metrics.get(key, 0) + (record[name] or 0)
        calls = metrics.setdefault("calls", [])
        if len(calls) < 64:
            calls.append(record)
        else:
            metrics["omitted_call_details"] = metrics.get("omitted_call_details", 0) + 1
