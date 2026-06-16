"""Tests for GitHub client helpers (issue_comment context loader)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import responses

from prevue.github.client import (
    CommentContext,
    load_comment_context,
    load_pr_context,
    read_comment_body,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPO_FULL = "owner/prevue"
ISSUE_NUMBER = 42
BASE_SHA = "base000def456789012345678901234567890abcd"
HEAD_SHA = "abc123def456789012345678901234567890abcd"


@pytest.fixture
def comment_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(FIXTURES_DIR / "issue_comment_event.json"))
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO_FULL)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")
    monkeypatch.setenv("PREVUE_ISSUE_NUMBER", str(ISSUE_NUMBER))
    monkeypatch.setenv("PREVUE_COMMENT_BODY", "/prevue review")
    monkeypatch.setenv("PREVUE_COMMENT_AUTHOR", "alice")


def _register_pull_for_comment_context(rsps: responses.RequestsMock) -> None:
    repo_payload = {
        "full_name": REPO_FULL,
        "name": "prevue",
        "owner": {"login": "owner", "type": "User"},
    }
    pr_payload = {
        "url": f"https://api.github.com/repos/{REPO_FULL}/pulls/{ISSUE_NUMBER}",
        "id": 1,
        "number": ISSUE_NUMBER,
        "state": "open",
        "title": "Test PR",
        "body": "Test body",
        "base": {
            "sha": BASE_SHA,
            "ref": "main",
            "repo": {
                "full_name": REPO_FULL,
                "name": "prevue",
                "owner": {"login": "owner", "type": "User"},
            },
        },
        "head": {
            "sha": HEAD_SHA,
            "ref": "feature/walking-skeleton",
            "repo": {
                "full_name": REPO_FULL,
                "name": "prevue",
                "owner": {"login": "owner", "type": "User"},
            },
        },
    }
    rsps.add(
        responses.GET,
        re.compile(rf"https://api\.github\.com(?::443)?/repos/{REPO_FULL}/?$"),
        json=repo_payload,
        status=200,
    )
    rsps.add(
        responses.GET,
        re.compile(rf"https://api\.github\.com(?::443)?/repos/{REPO_FULL}/pulls/{ISSUE_NUMBER}/?$"),
        json=pr_payload,
        status=200,
    )


@responses.activate
def test_load_comment_context_from_issue_comment_event(
    comment_github_env: None,
) -> None:
    _register_pull_for_comment_context(responses.mock)

    ctx = load_comment_context()

    assert isinstance(ctx, CommentContext)
    assert ctx.repo_full == REPO_FULL
    assert ctx.issue_number == ISSUE_NUMBER
    assert ctx.comment_body == "/prevue review"
    assert ctx.comment_author == "alice"
    assert ctx.author_association == "COLLABORATOR"
    assert ctx.head_sha == HEAD_SHA
    assert ctx.base_sha == BASE_SHA
    assert ctx.head_repo_full == REPO_FULL
    assert ctx.base_repo_full == REPO_FULL


@responses.activate
def test_load_comment_context_reads_body_from_path(
    comment_github_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    body_path = tmp_path / "comment.txt"
    body_path.write_text("/prevue dismiss abc123def4567890", encoding="utf-8")
    monkeypatch.delenv("PREVUE_COMMENT_BODY", raising=False)
    monkeypatch.setenv("PREVUE_COMMENT_BODY_PATH", str(body_path))
    _register_pull_for_comment_context(responses.mock)
    assert load_comment_context().comment_body == "/prevue dismiss abc123def4567890"


def test_read_comment_body_prefers_path_over_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    body_path = tmp_path / "comment.txt"
    body_path.write_text("from file", encoding="utf-8")
    monkeypatch.setenv("PREVUE_COMMENT_BODY", "from env")
    monkeypatch.setenv("PREVUE_COMMENT_BODY_PATH", str(body_path))
    assert read_comment_body() == "from file"


@responses.activate
def test_load_comment_context_no_pull_request_key_in_event(
    comment_github_env: None,
) -> None:
    """issue_comment payload has no top-level pull_request — must not KeyError."""
    with (FIXTURES_DIR / "issue_comment_event.json").open() as f:
        event = json.load(f)
    assert "pull_request" not in event

    _register_pull_for_comment_context(responses.mock)
    ctx = load_comment_context()
    assert ctx.head_sha == HEAD_SHA


@responses.activate
def test_load_comment_context_accepts_matching_pinned_head_sha(
    comment_github_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PREVUE_PR_HEAD_SHA", HEAD_SHA)
    _register_pull_for_comment_context(responses.mock)
    assert load_comment_context().head_sha == HEAD_SHA


@responses.activate
def test_load_comment_context_rejects_moved_head_after_pin(
    comment_github_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PREVUE_PR_HEAD_SHA", "deadbeef" + "0" * 32)
    _register_pull_for_comment_context(responses.mock)
    with pytest.raises(ValueError, match="PR head moved after authorization"):
        load_comment_context()


@pytest.fixture
def github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """PR-event env for load_pr_context regression."""
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(FIXTURES_DIR / "event_pull_request.json"))
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO_FULL)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")


def test_load_pr_context_regression_unchanged(github_env: None) -> None:
    ctx = load_pr_context()
    assert ctx.repo_full == REPO_FULL
    assert ctx.pr_number == ISSUE_NUMBER
    assert ctx.head_repo_full == REPO_FULL
    assert ctx.base_repo_full == REPO_FULL
