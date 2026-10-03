"""Run every case against every agent variant, with an on-disk cache.

The cache key covers the variant config, the case, and a fingerprint of the agent's code,
skills and data, so any prompt/skill change re-runs only what it affects.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel
from rich.progress import Progress

from .dataset import Case
from .scorers import Scores, judge_reply, score


class Variant(BaseModel):
    name: str
    model: str
    skills_dir: str = "skills"
    context_mode: str = "progressive"


class Record(BaseModel):
    variant: str
    case_id: str
    tags: list[str]
    repeat: int = 0
    result: dict | None = None
    error: str | None = None
    scores: Scores
    cached: bool = False


def load_variants(path: Path) -> tuple[dict[str, Variant], dict]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    variants = {n: Variant(name=n, **cfg) for n, cfg in raw["variants"].items()}
    return variants, raw.get("defaults", {})


def agent_fingerprint(skills_dir: str) -> str:
    """Hash of the agent package source, the chosen skills directory and the mock data."""
    import support_agent
    from support_agent.paths import default_data_dir, resolve_skills_dir

    h = hashlib.sha256()
    pkg = Path(support_agent.__file__).parent
    files = [p for p in pkg.glob("*.py")]  # code only; bundled skills/data are hashed below
    for root in (resolve_skills_dir(skills_dir), default_data_dir()):
        files += [p for p in root.rglob("*") if p.is_file() and p.suffix in {".md", ".json"}]
    for p in sorted(files):
        h.update(p.name.encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]


class Cache:
    def __init__(self, root: Path | None):
        self.root = root
        if root:
            root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(*parts) -> str:
        return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:24]

    def get(self, key: str) -> dict | None:
        if not self.root:
            return None
        p = self.root / f"{key}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put(self, key: str, value: dict) -> None:
        if self.root:
            (self.root / f"{key}.json").write_text(json.dumps(value), encoding="utf-8")


async def run_variant(
    variant: Variant,
    cases: list[Case],
    *,
    today: str,
    concurrency: int = 4,
    repeats: int = 1,
    cache: Cache,
    judge_model: str | None = None,
    progress: Progress | None = None,
) -> list[Record]:
    from support_agent.api import AgentConfig, SupportAgent

    cfg = AgentConfig(
        model=variant.model,
        skills_dir=variant.skills_dir,
        context_mode=variant.context_mode,
        today=today,
    )
    fp = agent_fingerprint(variant.skills_dir)
    sem = asyncio.Semaphore(concurrency)
    task = progress.add_task(variant.name, total=len(cases) * repeats) if progress else None

    async with SupportAgent(cfg) as agent:

        async def one(case: Case, rep: int) -> Record:
            key = Cache.key(variant.model_dump(), case.message, case.followups, today, fp, rep)
            hit = cache.get(key)
            result, error, cached = (hit, None, True) if hit else (None, None, False)
            if not hit:
                async with sem:
                    try:
                        r = await agent.triage(case.message, followups=list(case.followups))
                        result = r.model_dump(mode="json")
                        cache.put(key, result)
                    except Exception as exc:  # recorded as a failed case, never silently dropped
                        error = f"{type(exc).__name__}: {exc}"[:500]
            s = score(case, result)
            if judge_model and result:
                async with sem:
                    s.judge = await judge_reply(case, result, judge_model)
            if progress:
                progress.advance(task)
            return Record(
                variant=variant.name,
                case_id=case.id,
                tags=case.tags,
                repeat=rep,
                result=result,
                error=error,
                scores=s,
                cached=cached,
            )

        return await asyncio.gather(*(one(c, r) for c in cases for r in range(repeats)))
