"""Adapter + per-role model wiring for run_review (T-05, 10-THERMOS quick task).

Extracted from review.py: the engine-adapter-resolution kwarg building and the
per-role model dict resolution. The actual ``require_functional_adapter`` call
stays in review.py (it is patched directly as ``prevue.review.require_functional_adapter``
in the test suite — moving the call site here would silently stop tests from
being able to substitute a fake adapter), so this module only computes the
inputs review.py needs to make that call, plus the model-role dict derived
from the same EngineConfig.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prevue.config import resolve_engine_models_from_config

if TYPE_CHECKING:
    from prevue.config import EngineConfig


def adapter_factory_kwargs(engine_config: EngineConfig) -> dict[str, object]:
    """Build the raw_args/pricing kwargs for require_functional_adapter/get_adapter.

    T-07 (10-THERMOS quick task) threads raw_args/pricing at construction time
    via factory kwargs; this helper centralizes the "empty list -> None" and
    pricing pass-through so review.py's call site stays a single expression.
    """
    return {
        "raw_args": engine_config.raw_args or None,
        "pricing": engine_config.pricing,
    }


def resolve_role_models(engine_config: EngineConfig) -> dict[str, str | None]:
    """Per-role model dict (classify/review/consolidate) for the given EngineConfig.

    Direct pass-through to config.resolve_engine_models_from_config — kept as a
    review-local wrapper so review.py's import list documents the wiring step
    it belongs to (ENGN-09/D-11, Q-02).
    """
    return resolve_engine_models_from_config(engine_config)
