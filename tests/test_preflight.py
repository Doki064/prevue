"""Tests for workflow preflight parity with run_review."""

from __future__ import annotations

from prevue.preflight import (
    resolve_marker_for_scope,
    run_preflight_noop_check,
    should_skip_engine_install,
)

LAST = "abc123def456789012345678901234567890abcd"
HEAD = "def456789012345678901234567890abcdef12"


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
