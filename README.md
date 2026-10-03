# agent-eval-harness

[![CI](https://github.com/RahulBruh/agent-eval-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/RahulBruh/agent-eval-harness/actions/workflows/ci.yml)

A benchmarking harness that runs the same labeled tasks across agent configurations and reports **accuracy, tokens per task, cost and latency**, then blocks regressions in CI.

It evaluates [`skills-support-agent`](https://github.com/RahulBruh/skills-support-agent), a player-support triage agent whose domains are declarative `SKILL.md` files. The harness answers two questions about that agent: does it triage correctly, and what does that cost?

## Headline result (eval run 2026-10-03, 53 cases, Claude Haiku 4.5)

Restructuring the skill files and switching to progressive context loading **cut tokens per task by 72% (26,468 → 7,400) and cost per task by 65% ($0.0292 → $0.0102) while maintaining decision accuracy** (86.8% → 92.5%; the 95% CIs overlap, so this is "no regression", not a proven gain).

| variant | skills | context | accuracy (95% CI) | routing | escalation | priority | tokens/task | $/task | p50 latency |
|---|---|---|---|---|---|---|---|---|---|
| v1-inline-haiku *(before)* | v1 (verbose) | inline_all | 86.8% (75–93) | 100.0% | 94.2% | 87.0% | 26,468 | $0.0292 | 8.7s |
| v1-progressive-haiku | v1 (verbose) | progressive | 88.7% (77–95) | 100.0% | 94.2% | 91.3% | 10,154 | $0.0131 | 9.5s |
| v2-inline-haiku | v2 (concise) | inline_all | 88.7% (77–95) | 98.1% | 92.3% | 93.5% | 13,252 | $0.0161 | 9.3s |
| **v2-progressive-haiku** *(after)* | v2 (concise) | progressive | **92.5% (82–97)** | 96.2% | 94.2% | 95.7% | **7,400** | **$0.0102** | 9.2s |

The 2×2 ablation separates the two changes:

| change vs. *before* | tokens/task | $/task |
|---|---|---|
| Progressive loading only | −61.6% | −55.1% |
| Concise skill files only | −49.9% | −44.8% |
| **Both** | **−72.0%** | **−65.1%** |

Nearly all of the saving is **input** tokens (−74%). Output tokens are flat (+2%), as expected, since the agent's decisions are the same size.

Raw data: [`results/2026-10-03-baseline/`](results/2026-10-03-baseline/) (`results.json` holds every case, response, tool call and token count; there's also `summary.md` and `report.html`). A Sonnet 5.5 variant was in the matrix, but every call failed: Claude 5-generation models reject non-default `temperature`. The harness surfaced it as 53 errored cases rather than hiding it, and it's fixed in the agent. Sonnet numbers haven't been re-measured yet.

## What the evals found

Benchmarking is only useful if it changes something. This run led to these changes:

1. **A routing regression introduced by the token optimization.** With progressive loading, the router sees only skill *descriptions*. The concise v2 billing description listed billing *problems* but not billing *questions*, so "Do you accept PayPal?" (`bill-13`) and "What's your refund policy?" (`bill-16`) fell through to the human-escalation fallback. That's why routing accuracy dips from 100% to 96.2% in the *after* row. Fixed in [skills-support-agent@6301dfe](https://github.com/RahulBruh/skills-support-agent/commit/f04d307). Caveat: the fix was found on this same dataset, so its effect needs a held-out check.
2. **Ambiguous business rules.** Writing labels exposed rules with two defensible answers (pending charges, refunds outside policy, non-launch crashes). The rules were tightened in both skill versions *before* any model run, so the comparison stays fair ([commit](https://github.com/RahulBruh/skills-support-agent/commit/7086b9b)).
3. **Run-to-run variance is real.** A partial second run re-measured the unchanged *before* config at 81.1% vs 86.8%, a 3-case swing at temperature 0 ([note](results/2026-10-03-run2/NOTE.md)). Differences of a few points on 53 cases are noise, which is why every accuracy figure carries a Wilson 95% interval.
4. **Remaining real errors** (`v2-progressive-haiku`): `bug-09` escalates a PC crash that the rules say is P3 with no escalation. The model reasons that "no known issue" means escalate, which the rules only say for crashes on *launch*.

## How it works

```
datasets/triage_cases.yaml ──► runner ──► SupportAgent(config) ──► MCP tools
            │                    │                 │
            │            on-disk cache keyed by    └─► TriageResult (+ usage, latency)
            │            agent code+skills+data            │
            ▼            fingerprint                       ▼
        labels ─────────────────────────────────► scorers ──► metrics ──► results.json
                                                                        summary.md
                                                                        report.html
                                                                        gate (exit 1 on regression)
```

- **Dataset:** 60 hand-labeled cases across billing, account recovery, bug reports, connectivity, out-of-scope, multi-intent, multi-turn (scripted follow-up answers) and prompt-injection. Labels come from the skill rules and the mock backend data, never from model output. A [label changelog](datasets/triage_cases.yaml) records every label change and the reason for it. The 53-case result above predates the 7 connectivity cases.
- **Variants** ([`variants.yaml`](variants.yaml)): model × skill set × context-loading mode. The evaluation date is pinned (`today: 2026-10-03`), so date-based policies like the 14-day refund window are deterministic.
- **Scoring:** a case *passes* when routing, escalation, priority and reply-safety checks are all correct, for every check the case labels. Field-extraction recall and KB-citation hit rate are reported separately. An optional LLM judge (`--judge-model`) scores reply quality from 1–5 but is not part of the headline numbers.
- **Metrics:** accuracy with Wilson 95% CI, per-check accuracy, per-tag accuracy, input/output tokens per task, LLM calls per task, $ per task (from the [published price list](https://platform.claude.com/docs/en/about-claude/pricing)), and p50/p95 latency.
- **Cache:** results are keyed on a SHA-256 fingerprint of the agent's code, the chosen skills directory and the mock data. Editing one skill re-runs only the variants that load it.

## Usage

```bash
uv sync                                    # installs the agent from GitHub
export ANTHROPIC_API_KEY=...

uv run evalh cases                          # dataset stats by tag
uv run evalh run                            # all variants x all cases
uv run evalh run --variant v2-progressive-haiku --tag smoke --out results/smoke
uv run evalh compare results/<run>/results.json --base v1-inline-haiku --new v2-progressive-haiku
uv run evalh baseline results/<run>/results.json v2-progressive-haiku --tag smoke --out baselines/smoke.json
uv run evalh gate results/<run>/results.json --baseline baselines/smoke.json   # exit 1 on regression
```

## CI

- [`ci.yml`](.github/workflows/ci.yml): lint, unit tests for scorers/metrics/gate/cache, and **dataset integrity** (every label names a real skill, KB article and priority). No API key needed.
- [`evals.yml`](.github/workflows/evals.yml): full benchmark on manual dispatch only, so API spend is always intentional. Uploads the report as an artifact.
- In the agent repo, [`evals.yml`](https://github.com/RahulBruh/skills-support-agent/blob/main/.github/workflows/evals.yml) runs this harness's smoke set on every PR that touches skills, code or data. It fails the PR if accuracy drops more than 10 pp or tokens per task rise more than 25% against the [committed baseline](https://github.com/RahulBruh/skills-support-agent/blob/main/baselines/smoke-baseline.json). For example, running the gate against the verbose *before* config fails with `tokens_per_task rose 7,597 -> 26,468 (allowed +25%)`.

## Limitations

- 53–60 cases is enough to detect large effects (like the 72% token reduction) but not small accuracy differences. The CIs say so.
- Single run per variant. `--repeats N` is supported but wasn't used for the headline numbers, to limit spend.
- Mock backend data. The tools, schemas and policies are realistic, but no real player data is involved.
- Total API spend for everything in `results/` was about $5.
