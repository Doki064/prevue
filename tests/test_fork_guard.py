"""Fork PR guard — early exit before fetch/engine/post (SECR-01)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prevue.review import FORK_UNSUPPORTED_MSG, ForkPrUnsupported, run_review

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPO_FULL = "owner/prevue"


@pytest.fixture
def fork_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(FIXTURES_DIR / "event_pull_request_fork.json"))
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO_FULL)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")


def test_fork_pr_exits_early_without_side_effects(fork_github_env: None) -> None:
    mock_pr = MagicMock()

    with (
        patch("prevue.review.fetch_diff") as mock_fetch,
        patch("prevue.review.CopilotCliAdapter") as mock_adapter_cls,
        patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
        patch("prevue.review.upsert_sticky") as mock_upsert,
    ):
        with pytest.raises(ForkPrUnsupported, match="unsupported"):
            run_review()

        assert FORK_UNSUPPORTED_MSG in str(ForkPrUnsupported().args[0])
        mock_fetch.assert_not_called()
        mock_adapter_cls.assert_not_called()
        mock_upsert.assert_not_called()


def test_cli_fork_returns_exit_zero(
    fork_github_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    from prevue.cli import main

    with patch("prevue.cli.run_review", side_effect=ForkPrUnsupported()):
        code = main(["review"])

    assert code == 0
    assert FORK_UNSUPPORTED_MSG in capsys.readouterr().err
