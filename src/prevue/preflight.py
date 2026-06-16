"""Workflow preflight helpers shared with run_review (install-skip parity)."""

from __future__ import annotations

import os
import sys
import time

from github import GithubException

from prevue.github.client import get_authenticated_pull, load_pr_context
from prevue.github.comments import parse_marker_sha, read_newest_trusted_sticky_body


def resolve_marker_for_scope(
    last_sha: str | None,
    head_sha: str,
    *,
    incremental: bool,
    force_full: bool,
) -> str | None:
    """Mirror run_review marker_for_scope: when to pass last SHA into decide_scope."""
    if force_full:
        return None
    if incremental or last_sha == head_sha:
        return last_sha
    return None


def should_skip_engine_install(last_sha: str | None, head_sha: str) -> bool:
    """True when decide_scope(last_sha, head_sha) returns noop on the fast path.

    Same-SHA re-runs noop regardless of review.incremental — nothing changed to
    review, so skipping the engine CLI install matches Python (see
    test_incremental_false_same_sha_is_noop). /prevue review uses force_full.
    """
    return bool(last_sha) and last_sha == head_sha


_TRANSIENT_GITHUB_STATUSES = frozenset({429, 500, 502, 503, 504})
_AUTH_CONFIG_GITHUB_STATUSES = frozenset({401, 403})
_MAX_STICKY_FETCH_ATTEMPTS = 2


def resolve_sticky_sha_for_preflight() -> str | None:
    """Resolve last-reviewed SHA from STICKY_SHA env or trusted sticky via API."""
    sticky_env = os.environ.get("STICKY_SHA")
    if sticky_env is not None:
        return sticky_env or None

    if not os.environ.get("GITHUB_TOKEN"):
        return None

    for attempt in range(_MAX_STICKY_FETCH_ATTEMPTS):
        try:
            ctx = load_pr_context()
            pr = get_authenticated_pull(ctx)
            body = read_newest_trusted_sticky_body(pr)
            return parse_marker_sha(body) if body else None
        except GithubException as exc:
            status = getattr(exc, "status", None)
            if status in _AUTH_CONFIG_GITHUB_STATUSES:
                print(
                    f"prevue: preflight sticky fetch auth/config error (HTTP {status}); "
                    "aborting preflight",
                    file=sys.stderr,
                )
                raise
            if status in _TRANSIENT_GITHUB_STATUSES:
                if attempt + 1 < _MAX_STICKY_FETCH_ATTEMPTS:
                    print(
                        f"prevue: preflight sticky fetch transient error (HTTP {status}); retrying",
                        file=sys.stderr,
                    )
                    time.sleep(1)
                    continue
                print(
                    f"prevue: preflight sticky fetch transient error (HTTP {status}) after "
                    "retry; proceeding without marker (engine install will run)",
                    file=sys.stderr,
                )
                return None
            print(
                f"prevue: preflight sticky fetch failed (HTTP {status}); aborting preflight",
                file=sys.stderr,
            )
            raise
        except (KeyError, OSError, TypeError, ValueError) as exc:
            print(f"prevue: preflight sticky fetch config error: {exc}", file=sys.stderr)
            raise

    return None


def run_preflight_noop_check() -> bool:
    """Env-driven noop probe for the reusable workflow preflight step.

    Requires PR_HEAD_SHA. STICKY_SHA is optional; when unset, fetches the newest
    trusted sticky via API so custom bot owners match run_review parity.
    """
    head_sha = os.environ.get("PR_HEAD_SHA")
    if not head_sha:
        msg = "PR_HEAD_SHA is required for preflight noop check"
        raise ValueError(msg)
    last_sha = resolve_sticky_sha_for_preflight()
    return should_skip_engine_install(last_sha, head_sha)
