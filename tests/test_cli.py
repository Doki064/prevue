"""CLI entrypoint tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from prevue.cli import main
from prevue.engines.claude_code_cli import ClaudeAuthError
from prevue.engines.errors import AuthError, EngineFailure


def test_cli_catches_auth_error_subclass_exit_one(capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "prevue.cli.run_review",
        side_effect=ClaudeAuthError("CLAUDE_CODE_OAUTH_TOKEN is not set."),
    ):
        code = main(["review"])
    assert code == 1
    captured = capsys.readouterr()
    assert "CLAUDE_CODE_OAUTH_TOKEN is not set." in captured.err


def test_cli_catches_auth_error_base_exit_one(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("prevue.cli.run_review", side_effect=AuthError("credential missing")):
        code = main(["review"])
    assert code == 1
    assert "credential missing" in capsys.readouterr().err


def test_cli_emits_machine_output_on_auth_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-05 (10-THERMOS): an AuthError that propagates past run_review must still
    produce OUTP-05 machine output (result-file artifact), not skip it entirely —
    the workflow's artifact-upload step runs with if: always() and expects a file."""
    result_file = tmp_path / "prevue-result.json"
    monkeypatch.setenv("PREVUE_RESULT_FILE", str(result_file))
    with patch(
        "prevue.cli.run_review",
        side_effect=ClaudeAuthError("CLAUDE_CODE_OAUTH_TOKEN is not set."),
    ):
        code = main(["review"])

    assert code == 1
    assert result_file.exists(), "AuthError must still emit a result-file artifact"
    payload = json.loads(result_file.read_text())
    assert "CLAUDE_CODE_OAUTH_TOKEN is not set." in payload["summary_markdown"]


def test_cli_emits_machine_output_on_engine_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-05: same guarantee for a bare EngineFailure (e.g. CLI exited nonzero)."""
    result_file = tmp_path / "prevue-result.json"
    monkeypatch.setenv("PREVUE_RESULT_FILE", str(result_file))
    with patch("prevue.cli.run_review", side_effect=EngineFailure("Claude Code CLI exited 1")):
        code = main(["review"])

    assert code == 1
    assert result_file.exists(), "EngineFailure must still emit a result-file artifact"
