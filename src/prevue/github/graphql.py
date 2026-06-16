"""Thin GraphQL transport for PR review thread operations (D-08/D-10)."""

from __future__ import annotations

import os
import sys

import requests

GRAPHQL_URL = "https://api.github.com/graphql"
MAX_REVIEW_THREAD_PAGES = 20

REVIEW_THREADS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          diffSide
          comments(first: 1) {
            nodes { body author { login } }
          }
        }
      }
    }
  }
}
"""

RESOLVE_REVIEW_THREAD_MUTATION = """
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""


class GraphQLError(Exception):
    """GraphQL response carried an errors payload."""

    def __init__(self, errors: list | dict) -> None:
        self.errors = errors
        super().__init__(str(errors))


def _graphql(query: str, variables: dict) -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        # Surface a missing token as a GraphQLError so both callers (which already
        # catch GraphQLError and degrade gracefully) treat it like any other failure
        # instead of an uncaught KeyError — resolve_review_thread promises never to raise.
        raise GraphQLError([{"type": "MISSING_TOKEN", "message": "GITHUB_TOKEN not set"}])
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError as exc:
        # A non-JSON body (proxy/error HTML, truncated response) must degrade through the
        # callers' GraphQLError handlers, not raise a bare JSONDecodeError they don't catch.
        raise GraphQLError([{"type": "INVALID_JSON", "message": str(exc)[:200]}]) from exc
    if data.get("errors"):
        raise GraphQLError(data["errors"])
    # A well-formed GraphQL response always carries "data"; default to {} so a malformed
    # body raises a controlled GraphQLError below rather than a bare KeyError.
    return data.get("data") or {}


def fetch_review_threads(owner: str, repo: str, number: int) -> list[dict]:
    """Return review threads with id, resolution state, path, line, and first comment body.

    Raises GraphQLError (including for a missing GITHUB_TOKEN or null repository/PR nodes)
    and requests.RequestException (HTTP/transport errors) by design — every caller wraps
    this in a handler that logs and degrades to a no-thread lifecycle, so propagation is the
    intended contract, not an oversight.
    """
    threads: list[dict] = []
    cursor: str | None = None
    page_count = 0
    while True:
        page_count += 1
        variables: dict = {"owner": owner, "repo": repo, "number": number}
        if cursor is not None:
            variables["cursor"] = cursor
        data = _graphql(REVIEW_THREADS_QUERY, variables)
        # repository / pullRequest are nullable in a well-formed GraphQL response (e.g.
        # the repo or PR does not exist, or is not visible to the token). Guard each level
        # and raise a controlled GraphQLError instead of a TypeError/KeyError so callers
        # degrade gracefully through their existing handlers.
        repository = (data or {}).get("repository")
        pull_request = repository.get("pullRequest") if isinstance(repository, dict) else None
        review_threads = (
            pull_request.get("reviewThreads") if isinstance(pull_request, dict) else None
        )
        if not isinstance(review_threads, dict):
            raise GraphQLError(
                [{"type": "NULL_NODE", "message": "reviewThreads not present in response"}]
            )
        for node in review_threads.get("nodes") or []:
            if not isinstance(node, dict) or not node.get("id"):
                continue
            # `comments` can be present-but-null, so `node.get("comments", {})` would
            # return None and `.get(...)` on it would AttributeError — coalesce to {}.
            comment_nodes = (node.get("comments") or {}).get("nodes") or []
            first = comment_nodes[0] if comment_nodes else None
            body = (first.get("body") or "") if isinstance(first, dict) else ""
            threads.append(
                {
                    "id": node["id"],
                    "isResolved": bool(node.get("isResolved")),
                    "isOutdated": bool(node.get("isOutdated")),
                    "path": node.get("path"),
                    "line": node.get("line"),
                    # PullRequestReviewThread exposes the diff side as `diffSide`
                    # (DiffSide!), NOT `side` — querying `side` made the whole query
                    # fail with "Field 'side' doesn't exist", silently disabling thread
                    # resolution on every run. Keep the internal dict key as "side".
                    "side": node.get("diffSide"),
                    "body": body,
                }
            )
        page_info = review_threads.get("pageInfo") or {}
        if page_info.get("hasNextPage"):
            if page_count >= MAX_REVIEW_THREAD_PAGES:
                print(
                    f"prevue: reviewThreads pagination capped at "
                    f"{MAX_REVIEW_THREAD_PAGES} pages ({len(threads)} threads); "
                    "remaining threads not fetched",
                    file=sys.stderr,
                )
                break
        else:
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            # endCursor must not be null when hasNextPage is true; stop pagination
            # to avoid an infinite loop re-requesting the same page forever.
            print(
                "prevue: GraphQL reviewThreads pagination: hasNextPage=true but "
                "endCursor is null; stopping pagination",
                file=sys.stderr,
            )
            break
    return threads


def _log_resolve_failure(exc: Exception) -> None:
    if isinstance(exc, GraphQLError):
        err_type = "GraphQL"
        if isinstance(exc.errors, list) and exc.errors:
            first = exc.errors[0]
            if isinstance(first, dict) and first.get("type"):
                err_type = str(first["type"])
        print(f"prevue: review thread resolve failed ({err_type})", file=sys.stderr)
    elif isinstance(exc, requests.HTTPError) and exc.response is not None:
        print(
            f"prevue: review thread resolve failed (HTTP {exc.response.status_code})",
            file=sys.stderr,
        )
    else:
        print(
            f"prevue: review thread resolve failed ({type(exc).__name__})",
            file=sys.stderr,
        )


def resolve_review_thread(thread_id: str) -> bool:
    """Resolve a review thread; best-effort — never raises to caller.

    Returns True only when the mutation response confirms ``thread.isResolved``; a
    success-shaped-but-unresolved payload (or any GraphQL/transport error, including a
    missing GITHUB_TOKEN surfaced by _graphql) returns False rather than a false positive.
    """
    try:
        data = _graphql(RESOLVE_REVIEW_THREAD_MUTATION, {"threadId": thread_id})
    except (GraphQLError, requests.RequestException) as exc:
        _log_resolve_failure(exc)
        return False
    thread = (data.get("resolveReviewThread") or {}).get("thread") or {}
    return bool(thread.get("isResolved"))
