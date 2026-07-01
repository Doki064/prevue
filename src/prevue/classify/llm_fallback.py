"""Per-file LLM classification fallback for unmatched paths (CLSF-02, D-12)."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prevue.skills.models import Skill

from prevue.classify.models import CANONICAL_LABEL_ORDER, GENERAL_LABEL
from prevue.engines.base import EngineAdapter
from prevue.engines.errors import AuthError, EngineFailure
from prevue.engines.prompt import build_classify_prompt
from prevue.engines.tokens import estimate_tokens

FALLBACK_DISCLOSURE = "classification fallback unavailable — reviewed as general"
FALLBACK_FAILED_GLOB = "(llm fallback failed)"
FALLBACK_PARTIAL_GLOB = "(llm fallback partial)"
CLASSIFY_BATCH_SIZE = 100


def _chunk_paths(paths: list[str], batch_size: int) -> list[list[str]]:
    return [paths[i : i + batch_size] for i in range(0, len(paths), batch_size)]


def estimate_classify_tokens(paths: list[str], *, batch_size: int = CLASSIFY_BATCH_SIZE) -> int:
    """Estimate token cost of classifying paths via the LLM fallback."""
    total = 0
    for batch in _chunk_paths(paths, batch_size):
        total += estimate_tokens(build_classify_prompt(batch))
    return total


def _validate_labels(
    raw: dict[str, str],
    allowed: tuple[str, ...] | list[str],
) -> dict[str, str]:
    allowed_set = set(allowed)
    return {
        path: label
        for path, label in raw.items()
        if isinstance(path, str) and isinstance(label, str) and label in allowed_set
    }


def _classify_batch(
    paths: list[str],
    adapter: EngineAdapter,
    *,
    model: str | None = None,
) -> tuple[dict[str, str], int | None]:
    """Run one adapter.classify() call; return (validated_labels, real_tokens | None)."""
    try:
        # T-09a (10-THERMOS quick task): classify_with_tokens has a universal
        # base-class default (EngineAdapter.classify_with_tokens) — no more
        # hasattr duck-typing needed here.
        raw, real_tokens = adapter.classify_with_tokens(
            paths,
            list(CANONICAL_LABEL_ORDER),
            model=model,
        )
    except (
        NotImplementedError,
        AttributeError,
        AuthError,
        EngineFailure,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ):
        return {}, None

    return _validate_labels(raw, CANONICAL_LABEL_ORDER), real_tokens


def llm_classify(
    unmatched_paths: list[str],
    adapter: EngineAdapter,
    *,
    model: str | None = None,
    batch_size: int = CLASSIFY_BATCH_SIZE,
) -> tuple[dict[str, str], str | None, int | None]:
    """Classify only unmatched paths via the selected adapter; degrade on failure.

    Returns (labels, disclosure, real_tokens) where real_tokens is the sum of
    input+output tokens reported by the engine across all batches (json_envelope
    engines only). None means no real count available — caller should estimate.
    """
    if not unmatched_paths:
        return {}, None, None

    validated: dict[str, str] = {}
    total_tokens: int | None = None
    for batch in _chunk_paths(unmatched_paths, batch_size):
        batch_labels, batch_tokens = _classify_batch(batch, adapter, model=model)
        validated.update(batch_labels)
        if batch_tokens is not None:
            total_tokens = (total_tokens or 0) + batch_tokens

    if not validated:
        return {GENERAL_LABEL: FALLBACK_FAILED_GLOB}, FALLBACK_DISCLOSURE, total_tokens

    missing_paths = [path for path in unmatched_paths if path not in validated]
    if missing_paths:
        partial = dict(validated)
        partial[GENERAL_LABEL] = FALLBACK_PARTIAL_GLOB
        listed = ", ".join(missing_paths[:5])
        suffix = " …" if len(missing_paths) > 5 else ""
        disclosure = (
            f"classification fallback partial — reviewed {len(missing_paths)} "
            f"unmatched path(s) as general: {listed}{suffix}"
        )
        return partial, disclosure, total_tokens

    return validated, None, total_tokens


_RELEVANT_LABEL = "relevant"
_IRRELEVANT_LABEL = "irrelevant"
_SKILL_SELECT_ALLOWED: tuple[str, ...] = (_RELEVANT_LABEL, _IRRELEVANT_LABEL)


def llm_select_skills(
    candidate_skills: list[Skill],
    adapter: EngineAdapter,
    *,
    model: str | None = None,
    paths: list[str] | None = None,
    diff_text: str | None = None,
) -> set[str] | None:
    """Return skill names rated relevant via classify_skills; None on any error.

    None means the call degraded (caller may fall back or pass-through).
    Empty set means the LLM succeeded but rated every candidate irrelevant.
    """
    if not candidate_skills:
        return set()

    diff_excerpt = diff_text[:8000] if diff_text else None
    try:
        raw = adapter.classify_skills(
            candidate_skills,
            list(_SKILL_SELECT_ALLOWED),
            model=model,
            paths=paths,
            diff_excerpt=diff_excerpt,
        )
    except AuthError:
        raise
    except (
        NotImplementedError,
        AttributeError,
        EngineFailure,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ):
        return None

    return {
        name
        for name, label in raw.items()
        if isinstance(name, str) and isinstance(label, str) and label == _RELEVANT_LABEL
    }
