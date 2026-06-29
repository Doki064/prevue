"""CLI entrypoint tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from prevue.cli import main
from prevue.engines.claude_code_cli import ClaudeAuthError
from prevue.engines.errors import AuthError


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
