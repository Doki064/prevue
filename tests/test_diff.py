"""Tests for GitHub diff fetch (no checkout)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import responses

from prevue.github.client import PrContext, load_pr_context
from prevue.github.diff import fetch_diff

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPO_FULL = "owner/prevue"
PR_NUMBER = 42
BASE_SHA = "base000def456789012345678901234567890abcd"
HEAD_SHA = "abc123def456789012345678901234567890abcd"


@pytest.fixture
def github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point env at fixture event payload."""
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(FIXTURES_DIR / "event_pull_request.json"))
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO_FULL)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")


def _register_pull_api(rsps: responses.RequestsMock) -> None:
    with (FIXTURES_DIR / "pulls_files.json").open() as f:
        files_payload = json.load(f)

    repo_payload = {
        "full_name": REPO_FULL,
        "name": "prevue",
        "owner": {"login": "owner", "type": "User"},
    }

    pr_payload = {
        "url": f"https://api.github.com/repos/{REPO_FULL}/pulls/{PR_NUMBER}",
        "id": 1,
        "number": PR_NUMBER,
        "state": "open",
        "title": "Test PR",
        "body": "Test body",
        "base": {"sha": BASE_SHA, "ref": "main"},
        "head": {"sha": HEAD_SHA, "ref": "feature/walking-skeleton"},
    }

    rsps.add(
        responses.GET,
        re.compile(rf"https://api\.github\.com(?::443)?/repos/{REPO_FULL}/?$"),
        json=repo_payload,
        status=200,
    )
    rsps.add(
        responses.GET,
        re.compile(rf"https://api\.github\.com(?::443)?/repos/{REPO_FULL}/pulls/{PR_NUMBER}/?$"),
        json=pr_payload,
        status=200,
    )
    rsps.add(
        responses.GET,
        re.compile(
            rf"https://api\.github\.com(?::443)?/repos/{REPO_FULL}/pulls/{PR_NUMBER}/files/?$"
        ),
        json=files_payload,
        status=200,
    )


def test_load_pr_context_from_single_event_parse(github_env: None) -> None:
    ctx = load_pr_context()
    assert isinstance(ctx, PrContext)
    assert ctx.repo_full == REPO_FULL
    assert ctx.pr_number == PR_NUMBER
    assert ctx.head_repo_full == "owner/prevue"
    assert ctx.base_repo_full == "owner/prevue"


@responses.activate
def test_fetch_diff_returns_diff_bundle(github_env: None) -> None:
    _register_pull_api(responses.mock)

    bundle = fetch_diff()

    assert bundle.pr_number == PR_NUMBER
    assert bundle.base_sha == BASE_SHA
    assert bundle.head_sha == HEAD_SHA
    assert len(bundle.files) == 2

    patched = next(f for f in bundle.files if f.path == "src/prevue/github/diff.py")
    assert patched.status == "added"
    assert patched.additions == 24
    assert patched.patch is not None

    omitted = next(f for f in bundle.files if f.path == "assets/logo.png")
    assert omitted.patch is None
