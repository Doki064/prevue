"""Review gate policy — thresholds, conclusion ladder, placement (NOIS-02/03, OUTP-03)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from prevue.models import Finding

Severity = Literal["error", "warning", "info"]

SEVERITY_RANK: dict[str, int] = {"error": 0, "warning": 1, "info": 2}


class ReviewConfig(BaseModel):
    """Consumer review thresholds (D-12/D-13/D-16/D-18/D-20)."""

    model_config = ConfigDict(extra="forbid")

    min_severity_to_comment: Severity = "warning"
    # Independent of min_severity_to_fail — fail evaluates ALL findings (D-14).
    min_severity_to_fail: Severity | None = None
    max_inline_comments: int = Field(default=10, ge=0)
    # Default 120k tokens (~480k bytes at bytes/4) stays under MAX_PROMPT_BYTES (~250k tokens).
    max_input_tokens: int = Field(default=120000, ge=1)
    output_reserve_tokens: int = Field(default=12000, ge=0)

    @model_validator(mode="after")
    def _validate_token_budget(self) -> "ReviewConfig":
        if self.output_reserve_tokens > self.max_input_tokens:
            raise ValueError("review.output_reserve_tokens must be <= review.max_input_tokens")
        return self


def load_review_config(consumer_path: str | None = None) -> ReviewConfig:
    """Load review thresholds from consumer prevue.yml; defaults when absent."""
    if consumer_path is None:
        return ReviewConfig()
    path = Path(consumer_path)
    if not path.is_file():
        return ReviewConfig()
    consumer = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not consumer or not isinstance(consumer, dict):
        return ReviewConfig()
    if "review" not in consumer:
        return ReviewConfig()
    return ReviewConfig.model_validate(consumer["review"])


def conclude(
    findings: list[Finding],
    cfg: ReviewConfig,
    *,
    degraded: bool = False,
    partial: bool = False,
) -> str:
    """failure > neutral > success. Branch protection treats neutral as passing."""
    if degraded:
        return "neutral"
    if cfg.min_severity_to_fail is not None and any(
        SEVERITY_RANK[f.severity] <= SEVERITY_RANK[cfg.min_severity_to_fail] for f in findings
    ):
        return "failure"
    if findings:
        return "neutral"
    if partial:
        return "neutral"
    return "success"


Conclusion = Literal["success", "neutral", "failure"]
Placement = Literal["inline", "summary-only", "position-fallback"]


class PlacedFinding(BaseModel):
    finding: Finding
    placement: Placement


class GateResult(BaseModel):
    conclusion: Conclusion
    severity_counts: dict[str, int]
    placed: list[PlacedFinding]
    inline: list[Finding]
    config: ReviewConfig
    degraded: bool = False
    dropped_findings: int = 0


def apply_gate(
    findings: list[Finding],
    cfg: ReviewConfig,
    valid_lines: dict[str, dict[str, set[int]]],
    *,
    degraded: bool = False,
    dropped_findings: int = 0,
    partial: bool = False,
) -> GateResult:
    """Fixed-order gate pipeline: verdict/counts → threshold → position → budget."""
    # D-14: conclusion and severity_counts over ALL findings before partitioning.
    conclusion = conclude(findings, cfg, degraded=degraded, partial=partial)
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        severity_counts[finding.severity] += 1

    def meets_comment_threshold(severity: str) -> bool:
        return SEVERITY_RANK[severity] <= SEVERITY_RANK[cfg.min_severity_to_comment]

    def is_placeable(finding: Finding) -> bool:
        side_lines = valid_lines.get(finding.path, {}).get(finding.side)
        return side_lines is not None and finding.line in side_lines

    placements: dict[int, Placement] = {}
    candidates: list[tuple[int, Finding]] = []

    for index, finding in enumerate(findings):
        if not meets_comment_threshold(finding.severity):
            placements[index] = "summary-only"
        elif not is_placeable(finding):
            placements[index] = "position-fallback"
        else:
            candidates.append((index, finding))

    candidates.sort(key=lambda item: (SEVERITY_RANK[item[1].severity], item[0]))
    inline_indices = {index for index, _ in candidates[: cfg.max_inline_comments]}

    for index, _finding in candidates:
        if index in inline_indices:
            placements[index] = "inline"
        else:
            placements[index] = "summary-only"

    tier_order = {"error": 0, "warning": 1, "info": 2}
    ordered = sorted(
        enumerate(findings),
        key=lambda item: (tier_order[item[1].severity], item[0]),
    )
    placed = [
        PlacedFinding(finding=finding, placement=placements[index]) for index, finding in ordered
    ]
    inline = [finding for index, finding in candidates if index in inline_indices]

    return GateResult(
        conclusion=conclusion,  # type: ignore[arg-type]
        severity_counts=severity_counts,
        placed=placed,
        inline=inline,
        config=cfg,
        degraded=degraded,
        dropped_findings=dropped_findings,
    )


def verdict_title(gate: GateResult) -> str:
    if gate.degraded:
        return "⚠️ Structured findings unavailable — not blocking"
    if gate.conclusion == "success":
        return "✅ Pass — no findings"
    if gate.conclusion == "failure":
        return "❌ Fail — findings at or above fail threshold"
    return "⚠️ Findings — not blocking"


def severity_counts_line(gate: GateResult) -> str:
    parts: list[str] = []
    for severity in ("error", "warning", "info"):
        count = gate.severity_counts.get(severity, 0)
        if count:
            parts.append(f"{count} {severity}")
    return " · ".join(parts)


def thresholds_line(gate: GateResult) -> str:
    comment = gate.config.min_severity_to_comment
    fail = gate.config.min_severity_to_fail
    if fail is None:
        return f"Thresholds: comment ≥ {comment} · fail: off"
    return f"Thresholds: comment ≥ {comment} · fail ≥ {fail}"
