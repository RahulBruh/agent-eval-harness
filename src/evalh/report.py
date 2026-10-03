from __future__ import annotations

import html
import json
from pathlib import Path

from .runner import Record, Variant


def _pct(v: float | None) -> str:
    return "-" if v is None else f"{v * 100:.1f}%"


def _num(v: float | None) -> str:
    if v is None:
        return "-"
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:.4g}"


def _delta(a: float | None, b: float | None, pct_points: bool) -> str:
    if a is None or b is None:
        return "-"
    if pct_points:
        return f"{(b - a) * 100:+.1f} pp"
    return f"{(b - a) / a * 100:+.1f}%" if a else "-"


def summary_table(variants: dict[str, Variant], summaries: dict[str, dict]) -> str:
    head = (
        "| variant | model | skills | context | accuracy (95% CI) | routing | escalation | priority "
        "| tokens/task | $/task | p50 latency | errors |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for name, s in summaries.items():
        v = variants[name]
        lo, hi = s["accuracy_ci95"]
        rows.append(
            f"| {name} | {v.model} | {v.skills_dir} | {v.context_mode} "
            f"| {_pct(s['accuracy'])} ({lo * 100:.0f}-{hi * 100:.0f}) | {_pct(s['routing_acc'])} "
            f"| {_pct(s['escalation_acc'])} | {_pct(s['priority_acc'])} | {s['tokens_per_task']:,.0f} "
            f"| ${s['cost_per_task_usd']:.4f} | {s['latency_p50_s']:.1f}s | {s['errors']} |"
        )
    return head + "\n".join(rows) + "\n"


def compare_table(base_name: str, base: dict, new_name: str, new: dict) -> str:
    metrics = [
        ("accuracy", True),
        ("routing_acc", True),
        ("escalation_acc", True),
        ("priority_acc", True),
        ("kb_hit_rate", True),
        ("field_recall", True),
        ("input_tokens_per_task", False),
        ("output_tokens_per_task", False),
        ("tokens_per_task", False),
        ("cost_per_task_usd", False),
        ("latency_p50_s", False),
    ]
    lines = [f"| metric | {base_name} | {new_name} | change |", "|---|---|---|---|"]
    for key, is_rate in metrics:
        a, b = base.get(key), new.get(key)
        fmt = _pct if is_rate else _num
        lines.append(f"| {key} | {fmt(a)} | {fmt(b)} | {_delta(a, b, is_rate)} |")
    return "\n".join(lines) + "\n"


def write_results(
    out: Path,
    meta: dict,
    variants: dict[str, Variant],
    records: list[Record],
    summaries: dict[str, dict],
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": meta,
        "variants": {k: v.model_dump() for k, v in variants.items() if k in summaries},
        "summaries": summaries,
        "records": [r.model_dump(mode="json") for r in records],
    }
    (out / "results.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    md = [
        f"# Eval run: {meta['name']}\n",
        f"{meta['cases']} cases · agent fingerprint(s) "
        f"{', '.join(meta['fingerprints'].values())} · {meta['timestamp']}\n",
        summary_table(variants, summaries),
    ]
    for name, s in summaries.items():
        if s["failed_cases"]:
            md.append(f"\n**{name}** failed: {', '.join(s['failed_cases'])}\n")
    (out / "summary.md").write_text("\n".join(md), encoding="utf-8")
    (out / "report.html").write_text(_html(meta, variants, summaries), encoding="utf-8")


def _html(meta: dict, variants: dict[str, Variant], summaries: dict[str, dict]) -> str:
    max_tok = max((s["tokens_per_task"] for s in summaries.values()), default=1) or 1

    def bar(value: float, scale: float, label: str, cls: str) -> str:
        w = max(1.0, value / scale * 100)
        return (
            f'<div class="bar {cls}" style="width:{w:.1f}%"><span>{html.escape(label)}</span></div>'
        )

    rows = []
    for name, s in summaries.items():
        v = variants[name]
        rows.append(
            f"<tr><th>{html.escape(name)}<small>{html.escape(v.model)} · {v.skills_dir} · "
            f"{v.context_mode}</small></th>"
            f"<td>{bar(s['accuracy'], 1, _pct(s['accuracy']), 'acc')}</td>"
            f"<td>{bar(s['tokens_per_task'], max_tok, f'{s["tokens_per_task"]:,.0f}', 'tok')}</td>"
            f"<td>${s['cost_per_task_usd']:.4f}</td><td>{s['latency_p50_s']:.1f}s</td></tr>"
        )
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Agent Eval Report</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--muted:#666;--acc:#2f7d4f;--tok:#3b6bc4;--line:#e5e5e5}}
@media (prefers-color-scheme:dark){{:root{{--bg:#121212;--fg:#eee;--muted:#999;--line:#333}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px}}
main{{max-width:960px;margin:auto}} table{{width:100%;border-collapse:collapse}}
th,td{{padding:8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}}
th small{{display:block;color:var(--muted);font-weight:400}}
.bar{{height:22px;border-radius:4px;position:relative;min-width:2px}}
.bar span{{position:absolute;left:6px;top:1px;color:#fff;font-size:13px;white-space:nowrap}}
.acc{{background:var(--acc)}} .tok{{background:var(--tok)}}
.wrap{{overflow-x:auto}}
</style></head><body><main>
<h1>Agent eval: {html.escape(meta["name"])}</h1>
<p>{meta["cases"]} cases · {html.escape(meta["timestamp"])}</p>
<div class="wrap"><table><tr><th>variant</th><th>accuracy</th><th>tokens / task</th><th>$ / task</th>
<th>p50 latency</th></tr>{"".join(rows)}</table></div>
</main></body></html>"""
