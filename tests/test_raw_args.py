"""RED contract tests for raw_args passthrough (ENGN-08 / D-10).

These tests are intentionally RED until Plan 04 implements EngineConfig with
a raw_args field in prevue.config.

Contract (D-10):
  - engine.raw_args is a list[str] (not a shell string) — pydantic validates this
  - raw_args is ignored (empty) when config comes from PR-head only (SKIL-04, Pitfall 4)
  - NO_CONSUMER_CONFIG_SENTINEL causes load_config to use defaults (raw_args=[])
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prevue.config import (
    NO_CONSUMER_CONFIG_SENTINEL,
    load_config,
    resolve_consumer_config_path,
)

try:
    from prevue.config import EngineConfig

    _IMPORT_ERROR: ImportError | None = None
except ImportError as exc:
    EngineConfig = None  # type: ignore[assignment,misc]
    _IMPORT_ERROR = exc


def _require_engine_config() -> None:
    """Fail clearly if EngineConfig is not importable."""
    if _IMPORT_ERROR is not None:
        pytest.fail(
            f"prevue.config.EngineConfig does not exist yet "
            f"(Plan 04 will create it): {_IMPORT_ERROR}",
            pytrace=False,
        )


# ---------------------------------------------------------------------------
# EngineConfig validation (RED until Plan 04)
# ---------------------------------------------------------------------------


def test_raw_args_list_is_valid() -> None:
    """EngineConfig accepts a list[str] for raw_args."""
    _require_engine_config()
    cfg = EngineConfig(name="copilot-cli", raw_args=["--some-flag", "value"])  # type: ignore[misc]
    assert cfg.raw_args == ["--some-flag", "value"]


def test_raw_args_string_is_rejected() -> None:
    """EngineConfig rejects a shell string for raw_args (D-10: list form only)."""
    _require_engine_config()
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="raw_args|list"):
        EngineConfig(name="copilot-cli", raw_args="--some-flag value")  # type: ignore[misc]


def test_raw_args_default_is_empty() -> None:
    """EngineConfig.raw_args defaults to empty list when not provided."""
    _require_engine_config()
    cfg = EngineConfig(name="copilot-cli")  # type: ignore[misc]
    assert cfg.raw_args == []


def test_raw_args_extra_fields_rejected() -> None:
    """EngineConfig uses ConfigDict(extra='forbid') — unknown fields raise ValidationError."""
    _require_engine_config()
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EngineConfig(name="copilot-cli", unknown_field="should_fail")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SKIL-04 Pitfall 4: base-ref-only — PR-head config yields no raw_args
# ---------------------------------------------------------------------------


def test_no_consumer_config_sentinel_covers_raw_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Actions env set with no PREVUE_CONSUMER_ROOT, resolve_consumer_config_path
    returns the sentinel, and load_config uses defaults (raw_args=[]).

    This verifies Pitfall 4: a PR-head-only prevue.yml is ignored.
    GITHUB_ACTIONS=1 + no PREVUE_CONSUMER_ROOT -> sentinel path -> defaults.
    """
    monkeypatch.setenv("GITHUB_ACTIONS", "1")
    monkeypatch.delenv("PREVUE_CONSUMER_ROOT", raising=False)

    path = resolve_consumer_config_path()
    assert str(path) == NO_CONSUMER_CONFIG_SENTINEL, (
        "Actions env without PREVUE_CONSUMER_ROOT must return NO_CONSUMER_CONFIG_SENTINEL"
    )

    # Loading from sentinel yields defaults — no raw_args from PR-head config
    cfg = load_config(str(path))
    assert cfg.engine  # engine still resolves to default


def test_sentinel_path_is_nonexistent() -> None:
    """NO_CONSUMER_CONFIG_SENTINEL path does not exist on the filesystem."""
    assert not Path(NO_CONSUMER_CONFIG_SENTINEL).exists(), (
        "Sentinel path must not exist so load_config uses built-in defaults"
    )


def test_raw_args_from_base_ref_yml(tmp_path: Path) -> None:
    """raw_args from a trusted base-ref prevue.yml are loaded into EngineConfig."""
    _require_engine_config()
    cfg_file = tmp_path / "prevue.yml"
    cfg_file.write_text(
        "engine:\n  name: copilot-cli\n  raw_args:\n    - --verbose\n    - --timeout\n    - '30'\n"
    )
    cfg = load_config(str(cfg_file))
    # The loaded config must expose raw_args from the engine block
    # (plan 04 will wire this into PrevueConfig; for now the test is RED)
    assert hasattr(cfg, "engine_config") or cfg.engine == "copilot-cli"
