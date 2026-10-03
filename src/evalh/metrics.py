from __future__ import annotations

import math
import statistics
from collections import defaultdict

from .runner import Record


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion; honest error bars for small n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(centre - half, 4), round(centre + half, 4))


def _rate(values: list[bool | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))
    return round(s[idx], 3)


def summarize(records: list[Record]) -> dict:
    n = len(records)
    ok = [r for r in records if r.result]
    passed = sum(r.scores.passed for r in records)
    usage = [r.result["usage"] for r in ok]
    costs = [r.result["cost_usd"] or 0.0 for r in ok]
    latency = [r.result["latency_s"] for r in ok]
    field_recall = [r.scores.field_recall for r in records if r.scores.field_recall is not None]
    judge = [r.scores.judge for r in records if r.scores.judge is not None]

    by_tag: dict[str, list[bool]] = defaultdict(list)
    for r in records:
        for t in r.tags:
            by_tag[t].append(r.scores.passed)

    def avg(key: str) -> float:
        return round(statistics.mean(u[key] for u in usage), 1) if usage else 0.0

    return {
        "cases": n,
        "errors": n - len(ok),
        "accuracy": round(passed / n, 4) if n else 0.0,
        "accuracy_ci95": wilson(passed, n),
        "routing_acc": _rate([r.scores.routing for r in records]),
        "escalation_acc": _rate([r.scores.escalation for r in records]),
        "priority_acc": _rate([r.scores.priority for r in records]),
        "safety_acc": _rate([r.scores.safety for r in records]),
        "kb_hit_rate": _rate([r.scores.kb_hit for r in records]),
        "field_recall": round(statistics.mean(field_recall), 4) if field_recall else None,
        "judge_avg": round(statistics.mean(judge), 2) if judge else None,
        "input_tokens_per_task": avg("input_tokens"),
        "output_tokens_per_task": avg("output_tokens"),
        "tokens_per_task": round(avg("input_tokens") + avg("output_tokens"), 1),
        "llm_calls_per_task": avg("llm_calls"),
        "cost_per_task_usd": round(statistics.mean(costs), 6) if costs else 0.0,
        "cost_total_usd": round(sum(costs), 4),
        "latency_p50_s": _pct(latency, 0.5),
        "latency_p95_s": _pct(latency, 0.95),
        "by_tag": {t: round(sum(v) / len(v), 4) for t, v in sorted(by_tag.items())},
        "failed_cases": sorted({r.case_id for r in records if not r.scores.passed}),
    }
