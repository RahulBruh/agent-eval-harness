from pathlib import Path

import pytest

from evalh import gate
from evalh.dataset import Case, load_cases
from evalh.metrics import summarize, wilson
from evalh.report import compare_table, summary_table, write_results
from evalh.runner import Cache, Record, Variant, agent_fingerprint, load_variants
from evalh.scorers import score

ROOT = Path(__file__).parents[1]
CASES = ROOT / "datasets" / "triage_cases.yaml"


def result(**kw) -> dict:
    base = {
        "skill": "billing",
        "escalate": True,
        "priority": "P2",
        "reply": "We're on it.",
        "fields": {"account_id": "maya.r@example.com", "platform": "PC"},
        "kb_articles": ["KB-101"],
        "usage": {"input_tokens": 1000, "output_tokens": 200, "llm_calls": 4},
        "cost_usd": 0.002,
        "latency_s": 3.0,
    }
    return base | kw


def case(**expect) -> Case:
    return Case(id="t", tags=["billing", "smoke"], message="m", expect=expect)


# -- dataset integrity --------------------------------------------------------------------------


def test_dataset_labels_reference_real_skills_kb_and_priorities():
    from support_agent.paths import default_data_dir, resolve_skills_dir
    from support_agent.skills import load_skills

    skills = set(load_skills(resolve_skills_dir("skills"))) | {"general"}
    kb_ids = {p.stem for p in (default_data_dir() / "kb").glob("*.md")}
    cases = load_cases(CASES)
    assert len(cases) >= 50
    for c in cases:
        e = c.expect
        assert e.skill and set(e.skill) <= skills, c.id
        assert not e.priority or set(e.priority) <= {"P1", "P2", "P3", "P4"}, c.id
        assert not e.kb_any or set(e.kb_any) <= kb_ids, c.id
        assert all(isinstance(f, str) for f in c.followups), c.id


def test_smoke_subset_covers_every_domain():
    smoke = load_cases(CASES, tags=["smoke"])
    tags = {t for c in smoke for t in c.tags}
    assert {"billing", "account", "bug", "general", "injection", "multi-turn"} <= tags


def test_variants_file_parses():
    variants, defaults = load_variants(ROOT / "variants.yaml")
    assert defaults["today"] == "2026-10-03"
    assert {v.context_mode for v in variants.values()} == {"progressive", "inline_all"}


# -- scoring ------------------------------------------------------------------------------------


def test_all_correct_passes():
    s = score(
        case(
            skill="billing",
            escalate=True,
            priority="P2",
            fields={"account_id": ["acc-1001", "maya.r@"]},
            kb_any=["KB-101"],
        ),
        result(),
    )
    assert s.passed and s.routing and s.field_recall == 1.0 and s.kb_hit


def test_wrong_priority_fails_but_unlabeled_checks_are_skipped():
    s = score(case(priority=["P1"]), result())
    assert s.priority is False and s.routing is None and not s.passed


def test_acceptable_alternatives():
    assert score(
        case(skill=["account-recovery", "billing"], priority=["P2", "P3"]), result()
    ).passed


def test_safety_check_is_case_insensitive():
    s = score(
        case(reply_must_not_contain=["has been REFUNDED"]),
        result(reply="Your order has been refunded."),
    )
    assert s.safety is False and not s.passed


def test_errored_run_fails():
    assert score(case(skill="billing"), None).passed is False


def test_kb_miss_does_not_fail_the_decision():
    s = score(case(skill="billing", kb_any=["KB-999"]), result())
    assert s.kb_hit is False and s.passed


# -- metrics, gate, report ----------------------------------------------------------------------


def records(n_pass: int, n_fail: int, tokens: int = 1200) -> list[Record]:
    out = []
    for i in range(n_pass + n_fail):
        r = result(usage={"input_tokens": tokens - 200, "output_tokens": 200, "llm_calls": 4})
        c = case(skill="billing" if i < n_pass else "bug-report")
        out.append(Record(variant="v", case_id=f"c{i}", tags=c.tags, result=r, scores=score(c, r)))
    return out


def test_summary_metrics():
    s = summarize(records(8, 2))
    assert s["accuracy"] == 0.8 and s["routing_acc"] == 0.8
    assert s["tokens_per_task"] == 1200 and s["errors"] == 0
    assert s["failed_cases"] == ["c8", "c9"]
    assert s["by_tag"]["smoke"] == 0.8


def test_wilson_interval_brackets_point_estimate():
    lo, hi = wilson(45, 50)
    assert lo < 0.9 < hi and lo > 0.75


def test_gate_flags_accuracy_drop_and_token_growth():
    base = summarize(records(10, 0))
    assert gate.check(summarize(records(10, 0)), base) == []
    worse = summarize(records(8, 2, tokens=2000))
    failures = gate.check(worse, base)
    assert any("accuracy" in f for f in failures) and any("tokens" in f for f in failures)


def test_report_files(tmp_path):
    v = {"v": Variant(name="v", model="claude-haiku-4-5", skills_dir="skills")}
    recs = records(3, 1)
    summaries = {"v": summarize(recs)}
    meta = {"name": "t", "timestamp": "now", "cases": 4, "fingerprints": {"v": "abc"}}
    write_results(tmp_path, meta, v, recs, summaries)
    assert {"results.json", "summary.md", "report.html"} <= {p.name for p in tmp_path.iterdir()}
    assert "| v | claude-haiku-4-5 |" in summary_table(v, summaries)
    assert "+0.0 pp" in compare_table("a", summaries["v"], "b", summaries["v"])


# -- cache --------------------------------------------------------------------------------------


def test_cache_roundtrip(tmp_path):
    c = Cache(tmp_path)
    k = Cache.key({"model": "x"}, "msg", [], "2026-10-03", "fp", 0)
    assert c.get(k) is None
    c.put(k, {"a": 1})
    assert c.get(k) == {"a": 1}


def test_fingerprint_differs_between_skill_sets():
    assert agent_fingerprint("skills") != agent_fingerprint("skills_v1")


def test_dataset_rejects_unknown_expect_keys(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("cases:\n  - id: x\n    message: m\n    expect: {oops: 1}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(p)
