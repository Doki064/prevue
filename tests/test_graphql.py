"""Tests for GraphQL review-thread transport (D-08/D-10)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import responses

from prevue.github.graphql import (
    MAX_REVIEW_THREAD_PAGES,
    REVIEW_THREADS_QUERY,
    fetch_review_threads,
    resolve_review_thread,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GRAPHQL_URL = "https://api.github.com/graphql"
OWNER = "owner"
REPO = "prevue"
PR_NUMBER = 42


@pytest.fixture
def github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")


def _load_fixture(name: str) -> dict:
    with (FIXTURES_DIR / name).open() as f:
        return json.load(f)


def _register_graphql(rsps: responses.RequestsMock, payload: dict, *, status: int = 200) -> None:
    rsps.add(
        responses.POST,
        re.compile(rf"{re.escape(GRAPHQL_URL)}/?$"),
        json=payload,
        status=status,
    )


def test_review_threads_query_uses_valid_thread_side_field() -> None:
    """PullRequestReviewThread has `diffSide`, not `side`/`startSide`.

    Querying the non-existent `side` field made the whole reviewThreads query fail with
    "Field 'side' doesn't exist", silently disabling thread resolution on every CI run.
    Guard against the regression in the query text itself (fixtures can mask it).
    """
    assert "diffSide" in REVIEW_THREADS_QUERY
    assert re.search(r"\bside\b", REVIEW_THREADS_QUERY) is None
    assert re.search(r"\bstartSide\b", REVIEW_THREADS_QUERY) is None


@responses.activate
def test_fetch_review_threads_parses_ids_and_states(github_env: None) -> None:
    _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))

    threads = fetch_review_threads(OWNER, REPO, PR_NUMBER)

    assert len(threads) == 2
    open_thread = next(t for t in threads if t["id"] == "RT_kwDOExampleOpen0001")
    assert open_thread["isResolved"] is False
    assert open_thread["isOutdated"] is False
    assert open_thread["path"] == "src/prevue/review.py"
    assert open_thread["line"] == 142
    assert "Missing error handling" in open_thread["body"]


@responses.activate
def test_resolve_review_thread_returns_true_on_success(github_env: None) -> None:
    _register_graphql(responses.mock, _load_fixture("graphql_resolve_ok.json"))

    assert resolve_review_thread("RT_kwDOExampleOpen0001") is True


@responses.activate
def test_resolve_review_thread_forbidden_returns_false(capsys, github_env: None) -> None:
    _register_graphql(responses.mock, _load_fixture("graphql_forbidden.json"))

    assert resolve_review_thread("RT_kwDOExampleOpen0001") is False

    captured = capsys.readouterr()
    assert "prevue: review thread resolve failed" in captured.err
    assert "FORBIDDEN" in captured.err
    assert "ghp_test_token" not in captured.err
    assert "Bearer" not in captured.err


def test_resolve_review_thread_missing_token_returns_false(
    capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing GITHUB_TOKEN must degrade like any other failure, not raise KeyError."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    assert resolve_review_thread("RT_kwDOExampleOpen0001") is False
    assert "prevue: review thread resolve failed" in capsys.readouterr().err


@responses.activate
def test_fetch_review_threads_raises_graphql_error_on_null_pull_request(
    github_env: None,
) -> None:
    """Null repository/pullRequest yields a controlled GraphQLError, not TypeError."""
    from prevue.github.graphql import GraphQLError

    _register_graphql(responses.mock, {"data": {"repository": None}})

    with pytest.raises(GraphQLError):
        fetch_review_threads(OWNER, REPO, PR_NUMBER)


@responses.activate
def test_fetch_review_threads_tolerates_missing_comment_body(github_env: None) -> None:
    """A comment node without a body must not KeyError; body defaults to empty string."""
    payload = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "RT_x",
                                "isResolved": False,
                                "isOutdated": False,
                                "path": "a.py",
                                "line": 1,
                                "diffSide": "RIGHT",
                                "comments": {"nodes": [{"author": {"login": "x"}}]},
                            }
                        ],
                    }
                }
            }
        }
    }
    _register_graphql(responses.mock, payload)

    threads = fetch_review_threads(OWNER, REPO, PR_NUMBER)

    assert threads[0]["body"] == ""


@responses.activate
def test_fetch_review_threads_tolerates_null_comments_field(github_env: None) -> None:
    """A present-but-null `comments` field must not AttributeError."""
    payload = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "RT_x",
                                "isResolved": False,
                                "isOutdated": False,
                                "path": "a.py",
                                "line": 1,
                                "diffSide": "RIGHT",
                                "comments": None,
                            }
                        ],
                    }
                }
            }
        }
    }
    _register_graphql(responses.mock, payload)

    threads = fetch_review_threads(OWNER, REPO, PR_NUMBER)

    assert threads[0]["body"] == ""


@responses.activate
def test_graphql_non_json_body_raises_graphql_error(github_env: None) -> None:
    """A non-JSON response degrades as GraphQLError, not an uncaught JSONDecodeError."""
    from prevue.github.graphql import GraphQLError

    responses.add(
        responses.POST,
        re.compile(rf"{re.escape(GRAPHQL_URL)}/?$"),
        body="<html>502 Bad Gateway</html>",
        status=200,
        content_type="text/html",
    )

    with pytest.raises(GraphQLError):
        fetch_review_threads(OWNER, REPO, PR_NUMBER)


@responses.activate
def test_resolve_review_thread_false_when_response_not_resolved(github_env: None) -> None:
    """A success-shaped payload that does not confirm isResolved returns False."""
    _register_graphql(
        responses.mock,
        {"data": {"resolveReviewThread": {"thread": {"id": "RT_x", "isResolved": False}}}},
    )

    assert resolve_review_thread("RT_x") is False


@responses.activate
def test_fetch_idempotent_surfaces_already_resolved_threads(github_env: None) -> None:
    """Caller can skip resolve when isResolved=true (Pitfall 3 idempotency)."""
    _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))

    threads = fetch_review_threads(OWNER, REPO, PR_NUMBER)
    resolved = next(t for t in threads if t["id"] == "RT_kwDOExampleResolved01")

    assert resolved["isResolved"] is True
    assert resolved["isOutdated"] is True
    assert resolved["path"] == "src/prevue/github/diff.py"


@responses.activate
def test_fetch_review_threads_stops_at_max_pages(capsys, github_env: None) -> None:
    """Pagination guard logs when thread count exceeds MAX_REVIEW_THREAD_PAGES."""
    page = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                        "nodes": [
                            {
                                "id": f"RT_page_{i}",
                                "isResolved": False,
                                "isOutdated": False,
                                "path": "a.py",
                                "line": i,
                                "diffSide": "RIGHT",
                                "comments": {"nodes": [{"body": "x", "author": {"login": "bot"}}]},
                            }
                            for i in range(100)
                        ],
                    }
                }
            }
        }
    }
    for _ in range(MAX_REVIEW_THREAD_PAGES):
        _register_graphql(responses.mock, page)

    threads = fetch_review_threads(OWNER, REPO, PR_NUMBER)

    assert len(threads) == MAX_REVIEW_THREAD_PAGES * 100
    assert "pagination capped" in capsys.readouterr().err
