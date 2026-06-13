"""Engine adapter contract — typed data shape for fetch → engine → post."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChangedFile(BaseModel):
    path: str
    status: str  # added | modified | removed | renamed
    additions: int
    deletions: int
    patch: str | None = None  # unified-diff hunks; None when GitHub omits (large/binary)


class DiffBundle(BaseModel):
    pr_number: int
    base_sha: str
    head_sha: str
    files: list[ChangedFile]
    # deliberately NO pr title/body fields surfaced to the engine (D-07)


class ReviewRequest(BaseModel):
    diff: DiffBundle
    instructions: str
    budget_seconds: int = 300
    model: str | None = None


class Finding(BaseModel):
    path: str
    line: int = Field(ge=1)
    side: Literal["RIGHT", "LEFT"] = "RIGHT"
    severity: Literal["error", "warning", "info"]
    title: str
    body: str
    suggestion: str | None = None


class ReviewResult(BaseModel):
    summary_markdown: str
    findings: list[Finding] = Field(default_factory=list)
    degraded: bool = False
    dropped_findings: int = 0
    engine_meta: dict = Field(default_factory=dict)
