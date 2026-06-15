"""Per-file LLM classification fallback for unmatched paths (CLSF-02, D-12)."""

from __future__ import annotations

import json
import subprocess

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
) -> dict[str, str]:
    """Run one adapter.classify() call; return validated labels (maybe empty)."""
    try:
        raw = adapter.classify(
            paths,
            list(CANONICAL_LABEL_ORDER),
            model=model,
        )
    except (
        NotImplementedError,
        AuthError,
        EngineFailure,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ):
        return {}

    return _validate_labels(raw, CANONICAL_LABEL_ORDER)


def llm_classify(
    unmatched_paths: list[str],
    adapter: EngineAdapter,
    *,
    model: str | None = None,
    batch_size: int = CLASSIFY_BATCH_SIZE,
) -> tuple[dict[str, str], str | None]:
    """Classify only unmatched paths via the selected adapter; degrade on failure."""
    if not unmatched_paths:
        return {}, None

    validated: dict[str, str] = {}
    for batch in _chunk_paths(unmatched_paths, batch_size):
        validated.update(_classify_batch(batch, adapter, model=model))

    if not validated:
        return {GENERAL_LABEL: FALLBACK_FAILED_GLOB}, FALLBACK_DISCLOSURE

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
        return partial, disclosure

    return validated, None
