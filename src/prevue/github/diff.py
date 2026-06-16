"""Fetch PR diff via GitHub REST API (no checkout)."""

from __future__ import annotations

from github import GithubException

from prevue.github.client import get_authenticated_pull, load_pr_context
from prevue.github.positions import regions_changed
from prevue.models import ChangedFile, DiffBundle


def decide_scope(
    repo,
    last_sha: str | None,
    head_sha: str,
) -> tuple[str, set[str] | None, object | None]:
    """Classify full vs incremental vs noop from marker SHA ancestry (D-03).

    Returns (scope, in_scope_paths, comparison). in_scope_paths is set only for
    incremental. comparison is the repo.compare result when that call succeeded.
    Failing safe to full is never wrong — only more expensive.
    """
    if not last_sha:
        return "full", None, None
    if last_sha == head_sha:
        return "noop", None, None
    try:
        comparison = repo.compare(last_sha, head_sha)
    except GithubException:
        return "full", None, None
    if comparison.status == "identical":
        return "noop", None, comparison
    if comparison.status == "ahead" and comparison.merge_base_commit.sha == last_sha:
        return "incremental", {f.filename for f in comparison.files}, comparison
    return "full", None, comparison


def regions_from_comparison(
    comparison: object | None,
    in_scope_paths: set[str],
) -> dict[str, list[tuple[int, int]]]:
    """Region map from a compare result's micro-diff patches (D-09 incremental).

    Uses compare patches only — never cumulative PR file patches — so outdated
    resolve does not treat hunks from earlier pushes as changed this slice.
    """
    if comparison is None:
        return {}
    regions: dict[str, list[tuple[int, int]]] = {}
    for file in comparison.files:
        if file.filename in in_scope_paths and file.patch:
            regions[file.filename] = regions_changed(file.filename, file.patch)
    return regions


def fetch_diff_in_scope(in_scope_paths: set[str]) -> DiffBundle:
    """Build DiffBundle from pr.get_files() filtered to in-scope paths (D-02).

    Each file carries its full base..head patch from the PR files endpoint,
    not the compare micro-diff — compare only identifies which files changed.
    """
    ctx = load_pr_context()
    pr = get_authenticated_pull(ctx)
    files = [
        ChangedFile(
            path=f.filename,
            status=f.status,
            additions=f.additions,
            deletions=f.deletions,
            patch=getattr(f, "patch", None),
        )
        for f in pr.get_files()
        if f.filename in in_scope_paths
    ]
    return DiffBundle(
        pr_number=ctx.pr_number,
        base_sha=pr.base.sha,
        head_sha=pr.head.sha,
        files=files,
    )


def fetch_diff() -> DiffBundle:
    """Map pr.get_files() → DiffBundle; patch=None when GitHub omits hunks."""
    ctx = load_pr_context()
    pr = get_authenticated_pull(ctx)
    files = [
        ChangedFile(
            path=f.filename,
            status=f.status,
            additions=f.additions,
            deletions=f.deletions,
            patch=getattr(f, "patch", None),
        )
        for f in pr.get_files()
    ]
    return DiffBundle(
        pr_number=ctx.pr_number,
        base_sha=pr.base.sha,
        head_sha=pr.head.sha,
        files=files,
    )
