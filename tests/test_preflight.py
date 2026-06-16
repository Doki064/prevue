"""Tests for workflow preflight parity with run_review."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from prevue.preflight import (
    resolve_marker_for_scope,
    resolve_sticky_sha_for_preflight,
    run_preflight_noop_check,
    should_skip_engine_install,
)

LAST = "abc123def456789012345678901234567890abcd"
HEAD = "def456789012345678901234567890abcdef12"
STICKY_BODY = f"<!-- prevue:sticky head={HEAD} -->\n## Prevue Review\n"


def test_should_skip_engine_install_on_same_sha() -> None:
    assert should_skip_engine_install(LAST, LAST) is True


def test_should_not_skip_when_head_changed() -> None:
    assert should_skip_engine_install(LAST, HEAD) is False
    assert should_skip_engine_install(None, HEAD) is False


def test_resolve_marker_for_scope_incremental_off_same_sha() -> None:
    assert resolve_marker_for_scope(LAST, LAST, incremental=False, force_full=False) == LAST


def test_resolve_marker_for_scope_incremental_off_changed_sha() -> None:
    assert resolve_marker_for_scope(LAST, HEAD, incremental=False, force_full=False) is None


def test_run_preflight_noop_check_reads_env() -> None:
    import os

    os.environ["PR_HEAD_SHA"] = HEAD
    os.environ["STICKY_SHA"] = HEAD
    assert run_preflight_noop_check() is True
    os.environ["STICKY_SHA"] = ""
    assert run_preflight_noop_check() is False


def test_resolve_marker_for_scope_force_full() -> None:
    assert resolve_marker_for_scope(LAST, LAST, incremental=True, force_full=True) is None


def test_resolve_sticky_sha_for_preflight_fetches_trusted_sticky(monkeypatch) -> None:
    monkeypatch.delenv("STICKY_SHA", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    pr = MagicMock()
    with (
        patch("prevue.preflight.load_pr_context") as load_ctx,
        patch("prevue.preflight.get_authenticated_pull", return_value=pr),
        patch(
            "prevue.preflight.read_newest_trusted_sticky_body",
            return_value=STICKY_BODY,
        ),
    ):
        load_ctx.return_value = MagicMock()
        assert resolve_sticky_sha_for_preflight() == HEAD


def test_resolve_sticky_sha_preflight_transient_degrades_to_full_install(monkeypatch) -> None:
    from github import GithubException

    monkeypatch.delenv("STICKY_SHA", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    with (
        patch("prevue.preflight.load_pr_context"),
        patch(
            "prevue.preflight.get_authenticated_pull",
            side_effect=GithubException(503, "Service unavailable"),
        ),
    ):
        assert resolve_sticky_sha_for_preflight() is None


def test_run_preflight_noop_check_false_when_transient_sticky_fetch_exhausted(monkeypatch) -> None:
    from github import GithubException

    monkeypatch.delenv("STICKY_SHA", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("PR_HEAD_SHA", HEAD)
    with (
        patch("prevue.preflight.load_pr_context"),
        patch(
            "prevue.preflight.get_authenticated_pull",
            side_effect=GithubException(503, "Service unavailable"),
        ),
    ):
        assert run_preflight_noop_check() is False


def test_resolve_sticky_sha_for_preflight_auth_error_raises(monkeypatch) -> None:
    from github import GithubException

    monkeypatch.delenv("STICKY_SHA", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    with (
        patch("prevue.preflight.load_pr_context"),
        patch(
            "prevue.preflight.get_authenticated_pull",
            side_effect=GithubException(403, "Forbidden"),
        ),
        pytest.raises(GithubException),
    ):
        resolve_sticky_sha_for_preflight()


def test_resolve_sticky_sha_for_preflight_config_error_raises(monkeypatch) -> None:
    monkeypatch.delenv("STICKY_SHA", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    with (
        patch("prevue.preflight.load_pr_context", side_effect=KeyError("GITHUB_EVENT_PATH")),
        pytest.raises(KeyError),
    ):
        resolve_sticky_sha_for_preflight()


def test_resolve_sticky_sha_for_preflight_retries_transient_github_error(monkeypatch) -> None:
    from github import GithubException

    monkeypatch.delenv("STICKY_SHA", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    pr = MagicMock()
    responses = [GithubException(503, "Service unavailable"), pr]
    with (
        patch("prevue.preflight.load_pr_context"),
        patch("prevue.preflight.get_authenticated_pull", side_effect=responses),
        patch(
            "prevue.preflight.read_newest_trusted_sticky_body",
            return_value=STICKY_BODY,
        ),
    ):
        assert resolve_sticky_sha_for_preflight() == HEAD
