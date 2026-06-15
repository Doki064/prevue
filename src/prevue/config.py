"""Single-read consumer config loader for .github/prevue.yml (WKFL-03, D-05/D-07/D-08)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from prevue.classify.models import RuleSet
from prevue.classify.rules import load_default_rules, merge_rules
from prevue.engines.registry import DEFAULT_ENGINE
from prevue.gate import ReviewConfig

# Sentinel path that never exists on a runner; signals load_config() to use framework
# defaults when no trusted base-ref root is available in Actions (SKIL-04 fail-closed).
NO_CONSUMER_CONFIG_SENTINEL = "/nonexistent/prevue-no-consumer-config.yml"


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


class SkillsConfig(BaseModel):
    """Consumer skill overrides and caps (SKIL-03, D-05/D-07)."""

    model_config = ConfigDict(extra="forbid")

    exclude: list[str] = Field(default_factory=list)
    # Per-skill body cap: 64 KiB (65536) — one skill ≈ 16k tokens at bytes/4, a
    # generous ceiling for a focused guideline while bounding any single file.
    max_skill_bytes: int = Field(default=65536, ge=1)
    # Aggregate consumer-skill body cap: 256 KiB (262144) — ~64k tokens, roughly half
    # the 120k default review budget, leaving room for the diff itself.
    max_total_consumer_bytes: int = Field(default=262144, ge=1)
    # Count cap: 50 consumer skills — bounds per-PR loading work; well above the
    # handful a typical repo defines.
    max_consumer_skills: int = Field(default=50, ge=1)


class PrevueConfig(BaseModel):
    """Typed bundle from one prevue.yml read."""

    ruleset: RuleSet
    review: ReviewConfig
    skip: SkipConfig
    fallback: FallbackConfig
    skills: SkillsConfig
    engine: str


def resolve_consumer_config_path(
    config_path: str | None = None,
    *,
    consumer_root: str | None = None,
) -> Path:
    """Resolve config path under consumer checkout; reject traversal (WKFL-03).

    Containment on the *resolved* path (symlinks followed) is the single enforced
    invariant. A root always anchors the check: PREVUE_CONSUMER_ROOT/GITHUB_WORKSPACE
    when set, otherwise the current working directory.
    """
    raw = config_path or ".github/prevue.yml"
    rel = Path(raw)
    root_env = consumer_root or os.environ.get("PREVUE_CONSUMER_ROOT")

    if ".." in rel.parts:
        raise ValueError("config path must not contain '..'")

    if root_env:
        root_candidate: str | None = root_env
    elif os.environ.get("GITHUB_ACTIONS"):
        # In Actions, neither GITHUB_WORKSPACE nor cwd is guaranteed to be the base ref
        # — both can be the PR merge ref, so a PR-head prevue.yml could weaken its own
        # review thresholds (SKIL-04 gap). Fail closed: return a sentinel non-existent
        # path so load_config() uses framework defaults and never reads PR-head config.
        print(
            "prevue: PREVUE_CONSUMER_ROOT not set in Actions; consumer config ignored, "
            "using framework defaults (SKIL-04: workspace/cwd may be PR head, not base ref). "
            "Set PREVUE_CONSUMER_ROOT to the base-ref checkout to load consumer prevue.yml.",
            file=sys.stderr,
        )
        return Path(NO_CONSUMER_CONFIG_SENTINEL)
    else:
        root_candidate = os.environ.get("GITHUB_WORKSPACE")
    if root_candidate is None:
        if rel.is_absolute():
            raise ValueError(
                "absolute config path requires PREVUE_CONSUMER_ROOT or GITHUB_WORKSPACE"
            )
        root = Path.cwd().resolve()
    else:
        root = Path(root_candidate).resolve()

    resolved = (rel if rel.is_absolute() else root / rel).resolve()  # resolves symlinks
    if not resolved.is_relative_to(root):
        raise ValueError("config path escapes consumer checkout")
    return resolved


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
    """Load all prevue.yml sections from a single yaml.safe_load (D-08).

    consumer_path must be a path already validated by resolve_consumer_config_path()
    (the single source of truth for traversal/containment). Pass user-supplied paths
    through that resolver before calling this loader.
    """
    path = Path(consumer_path) if consumer_path is not None else Path(".github/prevue.yml")
    raw: dict = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if loaded and isinstance(loaded, dict):
            raw = loaded
    else:
        # Zero-config adoption is intentional (WKFL-01), but a missing file means
        # built-in rules, default skip policy, and classification.fallback.enabled=true
        # are silently in effect — surface that so consumers aren't surprised by
        # unexpected LLM classify calls or un-applied custom rules.
        print(
            f"prevue: no config file at {path}; using built-in defaults "
            "(classification.fallback.enabled=true)",
            file=sys.stderr,
        )

    ruleset = _ruleset_from_raw(raw)
    review = ReviewConfig.model_validate(raw.get("review", {}))
    skip = SkipConfig.model_validate(raw.get("skip", {}))
    classification = raw.get("classification") or {}
    if not isinstance(classification, dict):
        classification = {}
    fallback = FallbackConfig.model_validate(classification.get("fallback", {}))
    skills = SkillsConfig.model_validate(raw.get("skills", {}))
    engine = _resolve_engine(raw)

    return PrevueConfig(
        ruleset=ruleset,
        review=review,
        skip=skip,
        fallback=fallback,
        skills=skills,
        engine=engine,
    )
