"""Regression tests for EngineConfig's `_validate_pricing` field validator.

WR-02 (phase-10 review, iteration 3): the CR-01 fix that added
`_validate_pricing` to `EngineConfig` shipped with zero test coverage — no
test asserted `EngineConfig.model_validate` actually rejects a malformed
`engine.pricing` value. This mirrors `test_raw_args.py`'s structure for the
sibling `_validate_raw_args` validator so a future refactor (e.g. dropping
`mode="before"` during a Pydantic version bump, or loosening the
`isinstance` check) is caught by a failing test rather than silently
reopening the crash CR-01 fixed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from prevue.config import EngineConfig


def test_pricing_rejects_non_dict_value() -> None:
    """engine.pricing must be a mapping; a bare string is rejected."""
    with pytest.raises(ValidationError, match="mapping"):
        EngineConfig.model_validate({"name": "copilot-cli", "pricing": "not-a-dict"})


def test_pricing_rejects_non_dict_row() -> None:
    """Each row under engine.pricing must be a mapping or null."""
    with pytest.raises(ValidationError, match="mapping or null"):
        EngineConfig.model_validate(
            {"name": "copilot-cli", "pricing": {"gpt-4o": "not-a-dict"}}
        )


def test_pricing_accepts_none() -> None:
    """An absent/empty engine.pricing block is tolerated as 'no override'."""
    cfg = EngineConfig.model_validate({"name": "copilot-cli", "pricing": None})
    assert cfg.pricing is None


def test_pricing_default_is_none() -> None:
    """engine.pricing defaults to None when not provided at all."""
    cfg = EngineConfig.model_validate({"name": "copilot-cli"})
    assert cfg.pricing is None


def test_pricing_accepts_valid_row() -> None:
    """A well-formed pricing row (mapping of model -> pricing fields) is accepted as-is."""
    cfg = EngineConfig.model_validate(
        {
            "name": "copilot-cli",
            "pricing": {"gpt-4o": {"input_cost_per_token": 1e-6}},
        }
    )
    assert cfg.pricing == {"gpt-4o": {"input_cost_per_token": 1e-6}}


def test_pricing_accepts_null_row() -> None:
    """A null row under engine.pricing (explicit no-override for one model) is accepted."""
    cfg = EngineConfig.model_validate({"name": "copilot-cli", "pricing": {"gpt-4o": None}})
    assert cfg.pricing == {"gpt-4o": None}
