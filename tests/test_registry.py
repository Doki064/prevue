"""Tests for engine registry — resolve, default, fail-closed, Gemini skeleton."""

from __future__ import annotations

import pytest

from prevue.engines.copilot_cli import CopilotCliAdapter
from prevue.engines.registry import DEFAULT_ENGINE, ENGINES, UnknownEngineError, get_adapter
from tests.engine_helpers import make_sample_request


def test_resolves_copilot_cli() -> None:
    adapter = get_adapter("copilot-cli")
    assert isinstance(adapter, CopilotCliAdapter)


def test_default_engine_is_copilot_cli() -> None:
    assert DEFAULT_ENGINE == "copilot-cli"


def test_unknown_engine_raises_with_valid_names() -> None:
    with pytest.raises(UnknownEngineError, match="nope") as exc_info:
        get_adapter("nope")
    message = str(exc_info.value)
    assert "copilot-cli" in message
    assert "gemini-cli" in message
    for name in sorted(ENGINES):
        assert name in message


def test_gemini_registered_and_raises_not_implemented() -> None:
    adapter = get_adapter("gemini-cli")
    with pytest.raises(NotImplementedError, match="ENGN-04"):
        adapter.review(make_sample_request())
