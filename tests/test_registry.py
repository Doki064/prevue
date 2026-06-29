"""Tests for engine registry — resolve, default, fail-closed, antigravity functional."""

from __future__ import annotations

import pytest

from prevue.engines.cli_adapter import CliEngineAdapter
from prevue.engines.registry import (
    DEFAULT_ENGINE,
    ENGINES,
    UnknownEngineError,
    get_adapter,
    require_functional_adapter,
)


def test_resolves_copilot_cli() -> None:
    adapter = get_adapter("copilot-cli")
    assert isinstance(adapter, CliEngineAdapter)
    assert adapter.name == "copilot-cli"


def test_default_engine_is_copilot_cli() -> None:
    assert DEFAULT_ENGINE == "copilot-cli"


def test_unknown_engine_raises_with_valid_names() -> None:
    with pytest.raises(UnknownEngineError, match="nope") as exc_info:
        get_adapter("nope")
    message = str(exc_info.value)
    # All four engine names must appear in the error message
    for name in sorted(ENGINES):
        assert name in message, f"Expected {name!r} in error message: {message}"


def test_all_four_engines_registered() -> None:
    """All CLI engines from CLI_ENGINE_SPECS appear in ENGINES (auto-populated, D-01)."""
    assert "copilot-cli" in ENGINES
    assert "claude-code-cli" in ENGINES
    assert "cursor-cli" in ENGINES
    assert "antigravity-cli" in ENGINES


def test_antigravity_cli_is_functional() -> None:
    """antigravity-cli replaced the gemini skeleton and is now functional (D-12)."""
    adapter = get_adapter("antigravity-cli")
    assert isinstance(adapter, CliEngineAdapter)
    assert adapter.name == "antigravity-cli"


def test_require_functional_adapter_resolves_antigravity() -> None:
    """require_functional_adapter returns antigravity-cli (functional=True, D-12/D-03)."""
    adapter = require_functional_adapter("antigravity-cli")
    assert isinstance(adapter, CliEngineAdapter)
    assert adapter.name == "antigravity-cli"


def test_require_functional_adapter_unknown_raises() -> None:
    with pytest.raises(UnknownEngineError):
        require_functional_adapter("nope")


def test_skeleton_engines_removed() -> None:
    """SKELETON_ENGINES is gone; gemini-cli is no longer registered (D-03)."""
    from prevue.engines import registry

    assert not hasattr(registry, "SKELETON_ENGINES"), (
        "SKELETON_ENGINES must be removed from registry.py (D-03)"
    )
    assert "gemini-cli" not in ENGINES, (
        "gemini-cli skeleton was replaced by antigravity-cli; must not be in ENGINES"
    )
