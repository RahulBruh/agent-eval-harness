"""Regression gate: compare a run against a committed baseline and fail on regressions."""

from __future__ import annotations


def check(
    current: dict,
    baseline: dict,
    *,
    max_accuracy_drop: float = 0.05,
    max_token_increase: float = 0.25,
) -> list[str]:
    failures = []
    for key in ("accuracy", "routing_acc", "escalation_acc"):
        base, cur = baseline.get(key), current.get(key)
        if base is not None and cur is not None and base - cur > max_accuracy_drop:
            failures.append(
                f"{key} dropped {base:.1%} -> {cur:.1%} (allowed drop {max_accuracy_drop:.0%})"
            )
    base_tok, cur_tok = baseline.get("tokens_per_task"), current.get("tokens_per_task")
    if base_tok and cur_tok and (cur_tok - base_tok) / base_tok > max_token_increase:
        failures.append(
            f"tokens_per_task rose {base_tok:,.0f} -> {cur_tok:,.0f} "
            f"(allowed +{max_token_increase:.0%})"
        )
    if current.get("errors"):
        failures.append(f"{current['errors']} case(s) errored")
    return failures
