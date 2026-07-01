"""Single-read consumer config loader for .github/prevue.yml (WKFL-03, D-05/D-07/D-08).

Config Resolution Precedence (WKFL-05 / D-07)
===============================================
Three knobs have a caller-override layer above the consumer prevue.yml:

  workflow input > .github/prevue.yml > built-in defaults

Concretely, for each knob:

  1. engine:       PREVUE_ENGINE env  >  engine.name in yml  >  DEFAULT_ENGINE constant
  2. model:        PREVUE_MODEL env   >  COPILOT_MODEL env   >  engine.model in yml  >  None
  3. fallback model: (no env override)  >  classification.fallback.model in yml  >  None

``raw_args`` and ``pricing`` are parsed from the same single ``load_config`` read as
all other fields — they are therefore gated by ``resolve_consumer_config_path``'s
base-ref-only sentinel (SKIL-04/Pitfall 4).  A PR-head prevue.yml cannot inject CLI
flags or fake pricing data.
"""

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

# Declared precedence constant (WKFL-05 / D-07) — machine-readable form of the module
# docstring above.  Tests assert its presence with:
#   grep -qi 'workflow input > .*prevue.yml > .*default' src/prevue/config.py
CONFIG_PRECEDENCE = "workflow input > .github/prevue.yml > built-in defaults"


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


class EngineModels(BaseModel):
    """Per-role model overrides (ENGN-09 / D-11).

    Each role resolves: models.<role> else engine.model else None (engine default).
    Roles: classify, review, consolidate.  The consolidate slot is reserved for
    Phase 13 (QUAL-01) and is not consumed by the review pipeline today (D-13).
    """

    model_config = ConfigDict(extra="forbid")

    classify: str | None = None
    review: str | None = None
    consolidate: str | None = None  # D-13: reserved; Phase 13 (QUAL-01) will consume this


class EngineConfig(BaseModel):
    """Typed engine block from prevue.yml (ENGN-08/09, D-10/D-11).

    Parsed from the ``engine:`` YAML key in the single ``load_config`` read.
    Fields ``raw_args`` and ``pricing`` are base-ref-only (same gated read path —
    SKIL-04/Pitfall 4: PR-head prevue.yml cannot supply raw CLI flags or fake pricing).
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    model: str | None = None
    # models.<role> sub-block; stored as EngineModels or None when block absent.
    models: EngineModels = Field(default_factory=EngineModels)
    # raw_args: list[str] appended after framework argv (ENGN-08/D-10).
    # A shell string is rejected; list form only — no shell parsing, no shell=True.
    raw_args: list[str] = Field(default_factory=list)
    pricing: dict | None = None

    @field_validator("raw_args", mode="before")
    @classmethod
    def _validate_raw_args(cls, value: object) -> list[str]:
        """Reject a string raw_args; list[str] only (D-10: command injection guard).

        Also rejects lists with non-string elements (None, int, etc.) — Pydantic v2
        would silently coerce them (None → "None", 42 → "42"), producing invalid CLI flags.
        Exhaustive: any non-list, non-str scalar (int, float, bool, dict) is rejected here
        too, so callers always get the clean D-10 message instead of a generic Pydantic
        type-mismatch error.

        ``None`` is tolerated as a defense-in-depth special case (rather than rejected):
        an empty ``raw_args:`` YAML block parses to ``None``, not ``[]`` — a plausible
        consumer typo, not an attack. Treated as "no extra args" (see phase-10 review CR-02).
        """
        if value is None:
            return []
        if isinstance(value, str):
            raise ValueError(
                "engine.raw_args must be a list of strings (D-10: no shell string allowed). "
                f"Got str: {value!r}"
            )
        if not isinstance(value, list):
            raise ValueError(
                f"engine.raw_args must be a list of strings, "
                f"got {type(value).__name__!r}: {value!r}"
            )
        for i, item in enumerate(value):
            if not isinstance(item, str):
                raise ValueError(
                    f"engine.raw_args[{i}] must be a string, got {type(item).__name__!r}: {item!r}"
                )
        return value


class PrevueConfig(BaseModel):
    """Typed bundle from one prevue.yml read."""

    ruleset: RuleSet
    review: ReviewConfig
    skip: SkipConfig
    fallback: FallbackConfig
    skills: SkillsConfig
    engine: str  # resolved engine name (back-compat — PREVUE_ENGINE > yml > default)
    engine_config: EngineConfig = Field(default_factory=EngineConfig)  # full engine block


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


def _resolve_engine_models(raw: dict) -> dict[str, str | None]:
    """Per-role model resolution for classify / review / consolidate (ENGN-09/D-11).

    Resolution per role: models.<role> (yml) else engine.model (yml) else None.
    The consolidate role is resolved (slot reserved) but nothing consumes it this phase
    — merge_findings stays the deterministic fingerprint-dedup merge (D-13).
    Phase 13 (QUAL-01) will wire the consolidate model into the merge step.

    Returns a dict with keys 'classify', 'review', 'consolidate'.
    """
    engine_block = raw.get("engine") or {}
    if not isinstance(engine_block, dict):
        engine_block = {}

    # Single engine.model fallback (no env override — env model is applied at call-sites)
    single_model: str | None = engine_block.get("model") or None
    if single_model:
        single_model = str(single_model)

    # models sub-block: {classify: ..., review: ..., consolidate: ...}
    models_block = engine_block.get("models") or {}
    if not isinstance(models_block, dict):
        models_block = {}

    def _role(role: str) -> str | None:
        val = models_block.get(role)
        if val:
            return str(val)
        return single_model

    return {
        "classify": _role("classify"),
        "review": _role("review"),
        "consolidate": _role("consolidate"),  # D-13: reserved; consumed in Phase 13
    }


def resolve_engine_models_from_config(engine_config: EngineConfig) -> dict[str, str | None]:
    """Direct EngineConfig → per-role model dict (Q-02, 10-THERMOS).

    Replaces the review.py round-trip that reconstructed a fake raw YAML dict from
    EngineConfig fields just to pass it into _resolve_engine_models() — the round-trip
    existed because _resolve_engine_models() was designed for the raw YAML dict from
    load_config, not for the already-parsed typed model. This function takes the typed
    model directly.

    Resolution per role: models.<role> else engine.model else None (env override
    deliberately omitted — applied at call-sites per _resolve_engine_models docstring).
    """
    single_model = engine_config.model or None
    em = engine_config.models

    def _role(val: str | None) -> str | None:
        return val or single_model

    return {
        "classify": _role(em.classify),
        "review": _role(em.review),
        "consolidate": _role(em.consolidate),
    }


def resolve_review_model(review_model_from_config: str | None, env_model: str | None) -> str | None:
    """Apply the env-override layer to the per-role review model (T-02 fix — 10-THERMOS).

    Precedence: PREVUE_MODEL/COPILOT_MODEL env > models.review/engine.model (yml).
    Matches CONFIG_PRECEDENCE (knob 2) — env always wins over yml. Extracted as its
    own function so the operand order is unit-testable independent of review.py's
    1400-line review() body (_resolve_engine_models() deliberately omits env; this
    is the call-site env layer it defers to).
    """
    return env_model or review_model_from_config


def _build_engine_config(raw: dict) -> EngineConfig:
    """Parse the engine block from an already-loaded config dict (no second file read)."""
    engine_block = raw.get("engine") or {}
    if not isinstance(engine_block, dict):
        engine_block = {}
    return EngineConfig.model_validate(engine_block)


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
    engine_config = _build_engine_config(raw)

    return PrevueConfig(
        ruleset=ruleset,
        review=review,
        skip=skip,
        fallback=fallback,
        skills=skills,
        engine=engine,
        engine_config=engine_config,
    )
