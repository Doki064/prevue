"""Tests for GitHub diff fetch (no checkout)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import responses
from github import GithubException

from prevue.github.client import PrContext, get_repo, load_pr_context
from prevue.github.diff import (
    decide_scope,
    fetch_diff,
    fetch_diff_in_scope,
    regions_from_comparison,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPO_FULL = "owner/prevue"
PR_NUMBER = 42
BASE_SHA = "base000def456789012345678901234567890abcd"
HEAD_SHA = "abc123def456789012345678901234567890abcd"
LAST_SHA = "deadbeef123456789012345678901234567890ab"


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


def _register_compare(
    rsps: responses.RequestsMock,
    *,
    base: str,
    head: str,
    fixture_name: str,
) -> None:
    with (FIXTURES_DIR / fixture_name).open() as f:
        payload = json.load(f)
    rsps.add(
        responses.GET,
        re.compile(
            rf"https://api\.github\.com(?::443)?/repos/{REPO_FULL}/compare/{re.escape(base)}\.\.\.{re.escape(head)}(?:\?.*)?$"
        ),
        json=payload,
        status=200,
    )


@responses.activate
def test_decide_scope_first_run_no_marker(github_env: None) -> None:
    _register_pull_api(responses.mock)
    ctx = load_pr_context()
    repo = get_repo(ctx)

    scope, paths, _comparison = decide_scope(repo, None, HEAD_SHA)

    assert scope == "full"
    assert paths is None


@responses.activate
def test_decide_scope_same_sha_noop(github_env: None) -> None:
    _register_pull_api(responses.mock)
    ctx = load_pr_context()
    repo = get_repo(ctx)

    scope, paths, _cmp = decide_scope(repo, HEAD_SHA, HEAD_SHA)

    assert scope == "noop"
    assert paths is None


@responses.activate
def test_decide_scope_identical_noop(github_env: None) -> None:
    _register_pull_api(responses.mock)
    _register_compare(
        responses.mock,
        base=LAST_SHA,
        head=LAST_SHA,
        fixture_name="compare_identical.json",
    )
    ctx = load_pr_context()
    repo = get_repo(ctx)

    scope, paths, _cmp = decide_scope(repo, LAST_SHA, LAST_SHA)

    assert scope == "noop"
    assert paths is None


@responses.activate
def test_decide_scope_ahead_incremental(github_env: None) -> None:
    _register_pull_api(responses.mock)
    _register_compare(
        responses.mock,
        base=LAST_SHA,
        head=HEAD_SHA,
        fixture_name="compare_ahead.json",
    )
    ctx = load_pr_context()
    repo = get_repo(ctx)

    scope, paths, comparison = decide_scope(repo, LAST_SHA, HEAD_SHA)

    assert scope == "incremental"
    assert paths == {
        "src/prevue/github/diff.py",
        "src/prevue/review.py",
    }
    assert comparison is not None


@responses.activate
def test_decide_scope_diverged_force_push_full(github_env: None) -> None:
    _register_pull_api(responses.mock)
    _register_compare(
        responses.mock,
        base=LAST_SHA,
        head=HEAD_SHA,
        fixture_name="compare_diverged.json",
    )
    ctx = load_pr_context()
    repo = get_repo(ctx)

    scope, paths, _cmp = decide_scope(repo, LAST_SHA, HEAD_SHA)

    assert scope == "full"
    assert paths is None


@responses.activate
def test_decide_scope_ahead_merge_base_mismatch_full(github_env: None) -> None:
    """Belt-and-suspenders: ahead but merge_base != last_sha must not incremental."""
    _register_pull_api(responses.mock)
    with (FIXTURES_DIR / "compare_ahead.json").open() as f:
        payload = json.load(f)
    payload["merge_base_commit"]["sha"] = BASE_SHA
    responses.mock.add(
        responses.GET,
        re.compile(
            rf"https://api\.github\.com(?::443)?/repos/{REPO_FULL}/compare/{re.escape(LAST_SHA)}\.\.\.{re.escape(HEAD_SHA)}(?:\?.*)?$"
        ),
        json=payload,
        status=200,
    )
    ctx = load_pr_context()
    repo = get_repo(ctx)

    scope, paths, _cmp = decide_scope(repo, LAST_SHA, HEAD_SHA)

    assert scope == "full"
    assert paths is None


def test_decide_scope_compare_api_failure_returns_full() -> None:
    repo = MagicMock()
    repo.compare.side_effect = GithubException(503, {"message": "unavailable"}, headers={})

    scope, paths, _cmp = decide_scope(repo, LAST_SHA, HEAD_SHA)

    assert scope == "full"
    assert paths is None
    assert _cmp is None


@responses.activate
def test_regions_from_comparison_uses_compare_micro_diff(github_env: None) -> None:
    _register_pull_api(responses.mock)
    _register_compare(
        responses.mock,
        base=LAST_SHA,
        head=HEAD_SHA,
        fixture_name="compare_ahead.json",
    )
    ctx = load_pr_context()
    repo = get_repo(ctx)
    _scope, _paths, comparison = decide_scope(repo, LAST_SHA, HEAD_SHA)
    in_scope = {"src/prevue/github/diff.py"}

    regions = regions_from_comparison(comparison, in_scope)

    assert "src/prevue/github/diff.py" in regions


@responses.activate
def test_fetch_diff_in_scope_uses_full_pr_patch(github_env: None) -> None:
    """Incremental path sends full base..head patch from pr.get_files(), not compare micro-diff."""
    _register_pull_api(responses.mock)
    with (FIXTURES_DIR / "pulls_files.json").open() as f:
        full_files = json.load(f)
    target = "src/prevue/github/diff.py"
    full_patch = next(item["patch"] for item in full_files if item["filename"] == target)
    with (FIXTURES_DIR / "compare_ahead.json").open() as f:
        compare_payload = json.load(f)
    compare_micro_patch = next(
        item["patch"] for item in compare_payload["files"] if item["filename"] == target
    )
    assert full_patch != compare_micro_patch

    in_scope = {"src/prevue/github/diff.py"}
    bundle = fetch_diff_in_scope(in_scope)

    assert len(bundle.files) == 1
    assert bundle.files[0].path == "src/prevue/github/diff.py"
    assert bundle.files[0].patch == full_patch
    assert bundle.files[0].patch != compare_micro_patch
