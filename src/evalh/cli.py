from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress

from . import gate as gate_mod
from .dataset import load_cases
from .metrics import summarize
from .report import compare_table, summary_table, write_results
from .runner import Cache, agent_fingerprint, load_variants, run_variant

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(help="Evaluate and benchmark agent configurations.", no_args_is_help=True)
console = Console()

CasesOpt = Annotated[Path, typer.Option(help="Labeled cases YAML.")]
ListOpt = Annotated[list[str] | None, typer.Option()]


@app.command()
def run(
    cases_file: CasesOpt = Path("datasets/triage_cases.yaml"),
    variants_file: Annotated[Path, typer.Option()] = Path("variants.yaml"),
    variant: ListOpt = None,
    tag: ListOpt = None,
    case_id: ListOpt = None,
    concurrency: int = 4,
    repeats: int = 1,
    out: Annotated[Path, typer.Option()] = Path("results/latest"),
    cache_dir: Annotated[Path | None, typer.Option()] = Path(".evalcache"),
    no_cache: bool = False,
    judge_model: Annotated[str | None, typer.Option(help="Enable LLM-judge reply scoring.")] = None,
):
    """Run cases against variants and write results.json, summary.md and report.html."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY is not set.[/]")
        raise typer.Exit(2)
    variants, defaults = load_variants(variants_file)
    chosen = {k: v for k, v in variants.items() if not variant or k in variant}
    if not chosen:
        raise typer.BadParameter(f"no variants match {variant}; available: {list(variants)}")
    cases = load_cases(cases_file, tags=tag, ids=case_id)
    today = defaults.get("today", datetime.now(UTC).date().isoformat())
    cache = Cache(None if no_cache else cache_dir)

    async def main():
        records = []
        with Progress(console=console) as progress:
            for v in chosen.values():  # variants sequentially, cases concurrently
                records += await run_variant(
                    v,
                    cases,
                    today=today,
                    concurrency=concurrency,
                    repeats=repeats,
                    cache=cache,
                    judge_model=judge_model,
                    progress=progress,
                )
        return records

    records = asyncio.run(main())
    summaries = {n: summarize([r for r in records if r.variant == n]) for n in chosen}
    meta = {
        "name": out.name,
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "cases": len(cases),
        "repeats": repeats,
        "tags": tag or [],
        "today": today,
        "fingerprints": {n: agent_fingerprint(v.skills_dir) for n, v in chosen.items()},
    }
    write_results(out, meta, chosen, records, summaries)
    table = summary_table(chosen, summaries)
    console.print(table)
    console.print(f"Wrote {out / 'results.json'}, summary.md, report.html")
    if step_summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write((out / "summary.md").read_text(encoding="utf-8"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@app.command()
def compare(
    results: Path,
    base: Annotated[str, typer.Option(help="Baseline variant name.")],
    new: Annotated[str, typer.Option(help="Candidate variant name.")],
    other: Annotated[
        Path | None, typer.Option(help="Read --new from a different results file.")
    ] = None,
):
    """Delta table between two variants (same run, or across two runs)."""
    a = _load(results)["summaries"][base]
    b = _load(other or results)["summaries"][new]
    print(compare_table(base, a, new, b))


@app.command()
def baseline(results: Path, variant: str, out: Path = Path("baselines/baseline.json")):
    """Save one variant's summary from a run as the regression baseline."""
    data = _load(results)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"variant": variant, "meta": data["meta"], "summary": data["summaries"][variant]},
            indent=1,
        ),
        encoding="utf-8",
    )
    console.print(f"Baseline for {variant} written to {out}")


@app.command()
def gate(
    results: Path,
    baseline_file: Annotated[Path, typer.Option("--baseline")],
    variant: str | None = None,
    max_accuracy_drop: float = 0.05,
    max_token_increase: float = 0.25,
):
    """Exit 1 if accuracy dropped or tokens rose beyond tolerance vs the baseline."""
    base = _load(baseline_file)
    name = variant or base["variant"]
    current = _load(results)["summaries"][name]
    failures = gate_mod.check(
        current,
        base["summary"],
        max_accuracy_drop=max_accuracy_drop,
        max_token_increase=max_token_increase,
    )
    print(compare_table("baseline", base["summary"], name, current))
    if failures:
        for f in failures:
            console.print(f"[red]REGRESSION[/] {f}")
        raise typer.Exit(1)
    console.print("[green]Gate passed.[/]")


@app.command()
def cases(cases_file: CasesOpt = Path("datasets/triage_cases.yaml")):
    """Show case counts by tag."""
    all_cases = load_cases(cases_file)
    counts = Counter(t for c in all_cases for t in c.tags)
    console.print(f"{len(all_cases)} cases")
    for tag_name, n in counts.most_common():
        console.print(f"  {tag_name:12} {n}")


if __name__ == "__main__":
    app()
