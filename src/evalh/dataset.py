from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _as_list(v):
    return v if v is None or isinstance(v, list) else [v]


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: list[str] | None = None
    escalate: bool | None = None
    priority: list[str] | None = None
    fields: dict[str, list[str]] = Field(default_factory=dict)
    kb_any: list[str] | None = None
    reply_must_not_contain: list[str] = Field(default_factory=list)

    _norm = field_validator("skill", "priority", mode="before")(_as_list)

    @field_validator("fields", mode="before")
    @classmethod
    def _norm_fields(cls, v):
        return {k: _as_list(x) for k, x in (v or {}).items()}


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tags: list[str] = Field(default_factory=list)
    message: str
    followups: list[str] = Field(default_factory=list)
    expect: Expect


def load_cases(
    path: Path, tags: list[str] | None = None, ids: list[str] | None = None
) -> list[Case]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cases = [Case(**c) for c in raw["cases"]]
    dupes = {c.id for c in cases if sum(d.id == c.id for d in cases) > 1}
    if dupes:
        raise ValueError(f"duplicate case ids: {sorted(dupes)}")
    if tags:
        cases = [c for c in cases if set(tags) & set(c.tags)]
    if ids:
        cases = [c for c in cases if c.id in ids]
    return cases
