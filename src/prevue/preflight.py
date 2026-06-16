"""Workflow preflight helpers shared with run_review (install-skip parity)."""

from __future__ import annotations

import os


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


def run_preflight_noop_check() -> bool:
    """Env-driven noop probe for the reusable workflow preflight step.

    Requires PR_HEAD_SHA; optional STICKY_SHA from the sticky comment marker.
    """
    head_sha = os.environ.get("PR_HEAD_SHA")
    if not head_sha:
        msg = "PR_HEAD_SHA is required for preflight noop check"
        raise ValueError(msg)
    last_sha = os.environ.get("STICKY_SHA") or None
    return should_skip_engine_install(last_sha, head_sha)
