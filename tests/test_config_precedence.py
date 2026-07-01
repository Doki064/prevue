"""RED contract tests for config precedence matrix (WKFL-05 / D-07).

These tests pin the exact input > yml > default precedence for:
  - engine: PREVUE_ENGINE env > engine.name in yml > DEFAULT_ENGINE
  - fallback model: env (if any) > classification.fallback.model > None

Tests for _resolve_engine() (already exists in config.py) are GREEN by design —
they confirm the existing ladder is correct. Tests for _resolve_engine_models()
are RED until Plan 04 adds those functions.

Note: _resolve_model() (an earlier, superseded model-precedence resolver with
no production call path) was deleted (WR-03) — model resolution in production
goes through _resolve_engine_models()/resolve_review_model() instead, exercised
by the tests further below.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prevue.config import (
    _resolve_engine,
    load_config,
)
from prevue.engines.registry import DEFAULT_ENGINE

try:
    from prevue.config import _resolve_engine_models

    _IMPORT_ERROR: ImportError | None = None
except ImportError as exc:
    _resolve_engine_models = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc


def _require_new_resolvers() -> None:
    """Fail test clearly if _resolve_engine_models is not importable."""
    if _IMPORT_ERROR is not None:
        pytest.fail(
            f"prevue.config._resolve_engine_models does not exist yet "
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
        ("claude-code", "cursor-cli", "claude-code"),  # input beats yml
        (None, "cursor-cli", "cursor-cli"),  # yml beats default
        (None, None, DEFAULT_ENGINE),  # falls back to default
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
# Fallback model precedence — _resolve_engine_models (RED until Plan 04)
# ---------------------------------------------------------------------------


def test_fallback_model_from_yml(monkeypatch: pytest.MonkeyPatch) -> None:
    """_resolve_engine_models only reads the engine block — not classification.fallback.model.

    classification.fallback.model is consumed by review.py at runtime
    (_effective_classify_model = _classify_model or fallback_cfg.model), not by
    _resolve_engine_models.  When only the classification block is present, all
    role keys resolve to None.
    """
    _require_new_resolvers()
    monkeypatch.delenv("PREVUE_MODEL", raising=False)
    monkeypatch.delenv("COPILOT_MODEL", raising=False)

    raw = {"classification": {"fallback": {"model": "gpt-4o-mini"}}}
    models = _resolve_engine_models(raw)  # type: ignore[misc]
    assert models is not None
    # _resolve_engine_models does not read classification.fallback.model:
    # no engine block → all roles resolve to None
    assert models.get("classify") is None
    assert models.get("review") is None


# ---------------------------------------------------------------------------
# T-02 (10-THERMOS): review.py's env-override layer on top of per-role config
# ---------------------------------------------------------------------------


def test_resolve_review_model_env_beats_config() -> None:
    """PREVUE_MODEL/COPILOT_MODEL env must win over models.review/engine.model yml.

    Regression for T-02: review.py previously computed
    `_review_model_from_config or _env_model` (yml wins, inverted vs
    CONFIG_PRECEDENCE). resolve_review_model() is the extracted, testable
    call-site env layer that _resolve_engine_models() defers to.
    """
    from prevue.config import resolve_review_model

    assert resolve_review_model("yml-model", "env-model") == "env-model"


def test_resolve_review_model_falls_back_to_config_when_no_env() -> None:
    from prevue.config import resolve_review_model

    assert resolve_review_model("yml-model", None) == "yml-model"


def test_resolve_review_model_none_when_neither_set() -> None:
    from prevue.config import resolve_review_model

    assert resolve_review_model(None, None) is None


# ---------------------------------------------------------------------------
# T-08 (10-THERMOS quick task): resolve_classify_model — single canonical
# classify-model ladder, replacing the two identical inline ladders in review.py.
# ---------------------------------------------------------------------------


def test_resolve_classify_model_classify_wins() -> None:
    from prevue.config import resolve_classify_model

    assert resolve_classify_model("classify-model", "fallback-model", "env-model") == (
        "classify-model"
    )


def test_resolve_classify_model_fallback_wins_when_classify_unset() -> None:
    from prevue.config import resolve_classify_model

    assert resolve_classify_model(None, "fallback-model", "env-model") == "fallback-model"


def test_resolve_classify_model_env_wins_when_both_unset() -> None:
    from prevue.config import resolve_classify_model

    assert resolve_classify_model(None, None, "env-model") == "env-model"


def test_resolve_classify_model_none_when_all_unset() -> None:
    from prevue.config import resolve_classify_model

    assert resolve_classify_model(None, None, None) is None


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
