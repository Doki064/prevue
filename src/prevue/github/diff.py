"""Fetch PR diff via GitHub REST API (no checkout)."""

from __future__ import annotations

from prevue.github.client import get_authenticated_pull, load_pr_context
from prevue.models import ChangedFile, DiffBundle


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
