"""Single-read consumer config loader for .github/prevue.yml (WKFL-03, D-05/D-07/D-08)."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from prevue.classify.models import RuleSet
from prevue.classify.rules import load_default_rules, merge_rules
from prevue.engines.registry import DEFAULT_ENGINE
from prevue.gate import ReviewConfig


class SkipConfig(BaseModel):
    """Consumer skip policy (NOIS-01, D-13/14/15)."""

    model_config = ConfigDict(extra="forbid")

    review_bots: list[str] = Field(default_factory=list)
    skip_labels: list[str] = Field(default_factory=lambda: ["skip-review"])
    skip_title_patterns: list[str] = Field(default_factory=list)

    @field_validator("skip_title_patterns")
    @classmethod
    def _validate_skip_title_patterns(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid skip_title_patterns regex {pattern!r}: {exc}") from exc
        return patterns


class FallbackConfig(BaseModel):
    """Hybrid classification LLM fallback knobs (CLSF-02, D-09/10)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    model: str | None = None


class PrevueConfig(BaseModel):
    """Typed bundle from one prevue.yml read."""

    ruleset: RuleSet
    review: ReviewConfig
    skip: SkipConfig
    fallback: FallbackConfig
    engine: str


def resolve_consumer_config_path(
    config_path: str | None = None,
    *,
    consumer_root: str | None = None,
) -> Path:
    """Resolve config path under consumer checkout; reject traversal (WKFL-03)."""
    raw = config_path or ".github/prevue.yml"
    rel = Path(raw)
    root_env = consumer_root or os.environ.get("PREVUE_CONSUMER_ROOT")

    if rel.is_absolute():
        resolved = rel.resolve()
        if root_env:
            root = Path(root_env).resolve()
            if not resolved.is_relative_to(root):
                raise ValueError("config path must stay inside consumer checkout")
        return resolved

    if ".." in rel.parts:
        raise ValueError("config path must not contain '..'")

    if root_env:
        root = Path(root_env).resolve()
        resolved = (root / rel).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("config path escapes consumer checkout")
        return resolved

    return rel


def _ruleset_from_raw(raw: dict) -> RuleSet:
    """Build RuleSet from an already-loaded config dict (no second file read)."""
    merged = merge_rules(load_default_rules(), raw or None)
    return RuleSet.model_validate(
        {
            "ignore_globs": merged["ignore"],
            "label_rules": merged["labels"],
            "routing_map": merged["routing"],
        }
    )


def _resolve_engine(raw: dict) -> str:
    """Engine precedence: PREVUE_ENGINE env > prevue.yml engine.name > DEFAULT (D-05)."""
    env_engine = os.environ.get("PREVUE_ENGINE")
    if env_engine:
        return env_engine
    engine_block = raw.get("engine")
    if isinstance(engine_block, dict):
        name = engine_block.get("name")
        if name:
            return str(name)
    return DEFAULT_ENGINE


def load_config(consumer_path: str | None = None) -> PrevueConfig:
    """Load all prevue.yml sections from a single yaml.safe_load (D-08)."""
    path = Path(consumer_path) if consumer_path is not None else Path(".github/prevue.yml")
    raw: dict = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if loaded and isinstance(loaded, dict):
            raw = loaded

    ruleset = _ruleset_from_raw(raw)
    review = ReviewConfig.model_validate(raw.get("review", {}))
    skip = SkipConfig.model_validate(raw.get("skip", {}))
    classification = raw.get("classification") or {}
    if not isinstance(classification, dict):
        classification = {}
    fallback = FallbackConfig.model_validate(classification.get("fallback", {}))
    engine = _resolve_engine(raw)

    return PrevueConfig(
        ruleset=ruleset,
        review=review,
        skip=skip,
        fallback=fallback,
        engine=engine,
    )
