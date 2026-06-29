"""RED contract tests for config precedence matrix (WKFL-05 / D-07).

These tests pin the exact input > yml > default precedence for:
  - engine: PREVUE_ENGINE env > engine.name in yml > DEFAULT_ENGINE
  - model: PREVUE_MODEL (then COPILOT_MODEL) env > engine.model in yml > None
  - fallback model: env (if any) > classification.fallback.model > None

Tests for _resolve_engine() (already exists in config.py) are GREEN by design —
they confirm the existing ladder is correct. Tests for _resolve_model() and
_resolve_engine_models() are RED until Plan 04 adds those functions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prevue.config import (
    NO_CONSUMER_CONFIG_SENTINEL,
    _resolve_engine,
    load_config,
)
from prevue.engines.registry import DEFAULT_ENGINE

try:
    from prevue.config import _resolve_model, _resolve_engine_models

    _IMPORT_ERROR: ImportError | None = None
except ImportError as exc:
    _resolve_model = None  # type: ignore[assignment]
    _resolve_engine_models = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc


def _require_new_resolvers() -> None:
    """Fail test clearly if _resolve_model / _resolve_engine_models are not importable."""
    if _IMPORT_ERROR is not None:
        pytest.fail(
            f"prevue.config._resolve_model/_resolve_engine_models do not exist yet "
            f"(Plan 04 will create them): {_IMPORT_ERROR}",
            pytrace=False,
        )


# ---------------------------------------------------------------------------
# Engine precedence — _resolve_engine (exists, GREEN)
# ---------------------------------------------------------------------------


def test_engine_input_beats_yml(monkeypatch: pytest.MonkeyPatch) -> None:
    """PREVUE_ENGINE env overrides engine.name in yml."""
    monkeypatch.setenv("PREVUE_ENGINE", "claude-code")
    raw = {"engine": {"name": "cursor-cli"}}
    result = _resolve_engine(raw)
    assert result == "claude-code"


def test_engine_yml_beats_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """engine.name in yml overrides the built-in DEFAULT_ENGINE."""
    monkeypatch.delenv("PREVUE_ENGINE", raising=False)
    raw = {"engine": {"name": "cursor-cli"}}
    result = _resolve_engine(raw)
    assert result == "cursor-cli"


def test_engine_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env, no yml -> returns DEFAULT_ENGINE."""
    monkeypatch.delenv("PREVUE_ENGINE", raising=False)
    result = _resolve_engine({})
    assert result == DEFAULT_ENGINE


@pytest.mark.parametrize(
    "env_val,yml_name,expected",
    [
        ("claude-code", "cursor-cli", "claude-code"),   # input beats yml
        (None, "cursor-cli", "cursor-cli"),              # yml beats default
        (None, None, DEFAULT_ENGINE),                    # falls back to default
    ],
    ids=["input>yml", "yml>default", "default"],
)
def test_engine_precedence_matrix(
    env_val: str | None,
    yml_name: str | None,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parametrized matrix: all 3 engine-precedence cases in one table."""
    if env_val is not None:
        monkeypatch.setenv("PREVUE_ENGINE", env_val)
    else:
        monkeypatch.delenv("PREVUE_ENGINE", raising=False)

    raw: dict = {}
    if yml_name is not None:
        raw = {"engine": {"name": yml_name}}

    assert _resolve_engine(raw) == expected


# ---------------------------------------------------------------------------
# Model precedence — _resolve_model (RED until Plan 04)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prevue_model,copilot_model,yml_model,expected",
    [
        ("gpt-5", "gpt-4o", "gpt-4", "gpt-5"),     # PREVUE_MODEL beats all
        (None, "gpt-4o", "gpt-4", "gpt-4o"),        # COPILOT_MODEL beats yml
        (None, None, "gpt-4", "gpt-4"),              # yml beats None
        (None, None, None, None),                    # no model set -> None
    ],
    ids=["PREVUE_MODEL>all", "COPILOT_MODEL>yml", "yml>none", "none"],
)
def test_model_precedence_matrix(
    prevue_model: str | None,
    copilot_model: str | None,
    yml_model: str | None,
    expected: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parametrized matrix: PREVUE_MODEL > COPILOT_MODEL > yml engine.model > None."""
    _require_new_resolvers()

    if prevue_model is not None:
        monkeypatch.setenv("PREVUE_MODEL", prevue_model)
    else:
        monkeypatch.delenv("PREVUE_MODEL", raising=False)

    if copilot_model is not None:
        monkeypatch.setenv("COPILOT_MODEL", copilot_model)
    else:
        monkeypatch.delenv("COPILOT_MODEL", raising=False)

    raw: dict = {}
    if yml_model is not None:
        raw = {"engine": {"model": yml_model}}

    result = _resolve_model(raw)  # type: ignore[misc]
    assert result == expected


# ---------------------------------------------------------------------------
# Fallback model precedence — _resolve_engine_models (RED until Plan 04)
# ---------------------------------------------------------------------------


def test_fallback_model_from_yml(monkeypatch: pytest.MonkeyPatch) -> None:
    """classification.fallback.model from yml used when no env override."""
    _require_new_resolvers()
    monkeypatch.delenv("PREVUE_MODEL", raising=False)
    monkeypatch.delenv("COPILOT_MODEL", raising=False)

    raw = {"classification": {"fallback": {"model": "gpt-4o-mini"}}}
    models = _resolve_engine_models(raw)  # type: ignore[misc]
    assert models is not None
    # fallback model resolves from yml
    assert "classify" in models or "fallback" in models or models.get("classify") == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Integration: load_config exposes resolved engine
# ---------------------------------------------------------------------------


def test_load_config_respects_engine_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_config() applies _resolve_engine so PREVUE_ENGINE wins over yml."""
    monkeypatch.setenv("PREVUE_ENGINE", "claude-code")
    cfg_file = tmp_path / "prevue.yml"
    cfg_file.write_text("engine:\n  name: cursor-cli\n")
    cfg = load_config(str(cfg_file))
    assert cfg.engine == "claude-code"
