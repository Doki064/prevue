"""Classification stage models — RuleSet config and ClassificationResult output."""

from __future__ import annotations

from pydantic import BaseModel, Field

CANONICAL_LABEL_ORDER: tuple[str, ...] = (
    "security",
    "frontend",
    "backend",
    "data",
    "infra",
    "general",
)
GENERAL_LABEL = "general"


class RuleSet(BaseModel):
    """Built-in + consumer classification rules (D-04, ROUT-01)."""

    ignore_globs: list[str] = Field(default_factory=list)
    label_rules: dict[str, list[str]] = Field(default_factory=dict)
    routing_map: dict[str, str] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    """Deterministic classify output threaded to sticky Metadata (D-09)."""

    labels: dict[str, str] = Field(default_factory=dict)  # label → matched glob
    bundles: list[str] = Field(default_factory=list)
    dropped_count: int = 0
