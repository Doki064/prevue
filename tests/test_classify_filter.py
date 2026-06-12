"""Tests for filter_diff — drop ignored files before classification (D-08)."""

from __future__ import annotations

import pytest

from prevue.classify.filter import filter_diff
from prevue.models import ChangedFile, DiffBundle

PR_NUMBER = 1
BASE_SHA = "base000000000000000000000000000000000000"
HEAD_SHA = "head000000000000000000000000000000000000"


def _file(path: str) -> ChangedFile:
    return ChangedFile(path=path, status="modified", additions=1, deletions=0, patch="@@")


def _bundle(*paths: str) -> DiffBundle:
    return DiffBundle(
        pr_number=PR_NUMBER,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        files=[_file(p) for p in paths],
    )


def test_filter_diff_drops_lockfiles() -> None:
    diff = _bundle("src/App.tsx", "pkg/uv.lock")
    reduced, dropped = filter_diff(diff, ["**/*.lock"])

    assert [f.path for f in reduced.files] == ["src/App.tsx"]
    assert [f.path for f in dropped] == ["pkg/uv.lock"]


def test_filter_diff_does_not_mutate_original() -> None:
    diff = _bundle("src/App.tsx", "pkg/uv.lock")
    original_paths = [f.path for f in diff.files]

    reduced, _ = filter_diff(diff, ["**/*.lock"])

    assert [f.path for f in diff.files] == original_paths
    assert reduced is not diff


@pytest.mark.parametrize(
    ("paths", "ignore", "kept", "dropped_paths"),
    [
        (("README.md",), ["**/*.lock"], ["README.md"], []),
        (("node_modules/pkg/index.js",), ["**/node_modules/**"], [], ["node_modules/pkg/index.js"]),
    ],
)
def test_filter_diff_cases(
    paths: tuple[str, ...],
    ignore: list[str],
    kept: list[str],
    dropped_paths: list[str],
) -> None:
    diff = _bundle(*paths)
    reduced, dropped = filter_diff(diff, ignore)
    assert [f.path for f in reduced.files] == kept
    assert [f.path for f in dropped] == dropped_paths
