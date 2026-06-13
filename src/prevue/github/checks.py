"""GitHub Check Run merge gate — prevue/review on PR head SHA (OUTP-03, D-08/D-09/D-10).

Always use the caller-supplied PR head SHA (DiffBundle.head_sha). Never use
GITHUB_SHA — that is the merge commit on pull_request events, not the PR head.
"""

from __future__ import annotations

import sys

from github import GithubException
from github.Repository import Repository

from prevue.gate import GateResult, severity_counts_line, thresholds_line, verdict_title

CHECK_NAME = "prevue/review"


def _render_check_output(gate: GateResult, sticky_url: str | None) -> dict:
    """Compact check panel: verdict title + counts in title; thresholds + sticky link in summary."""
    title = verdict_title(gate)
    counts = severity_counts_line(gate)
    if counts:
        title = f"{title} ({counts})"

    summary = thresholds_line(gate)
    if sticky_url:
        summary += f"\n\nFull findings index in the [Prevue Review comment]({sticky_url})."

    return {"title": title, "summary": summary}


def conclude_review_check(
    repo: Repository,
    head_sha: str,
    gate: GateResult,
    *,
    sticky_url: str | None = None,
) -> bool:
    """Post a single completed check run concluding with the gate verdict."""
    try:
        repo.create_check_run(
            name=CHECK_NAME,
            head_sha=head_sha,
            status="completed",
            conclusion=gate.conclusion,
            output=_render_check_output(gate, sticky_url),
        )
    except GithubException as exc:
        status = getattr(exc, "status", "unknown")
        print(
            f"prevue: check-run POST failed (HTTP {status}, conclusion={gate.conclusion})",
            file=sys.stderr,
        )
        return False
    return True


def conclude_skip_check(
    repo: Repository,
    head_sha: str,
    *,
    dropped_count: int | None = None,
    conclusion: str = "success",
    reason: str | None = None,
) -> bool:
    """Post completed skip check — success for empty-PR, neutral for bot/label/title (D-09/D-16)."""
    if reason is not None:
        output = {"title": "review skipped", "summary": reason}
    else:
        output = {
            "title": "no reviewable files",
            "summary": f"{dropped_count} filtered file(s) — nothing to review.",
        }
    try:
        repo.create_check_run(
            name=CHECK_NAME,
            head_sha=head_sha,
            status="completed",
            conclusion=conclusion,
            output=output,
        )
    except GithubException as exc:
        status = getattr(exc, "status", "unknown")
        detail = reason or f"dropped={dropped_count}"
        print(
            f"prevue: skip check-run POST failed (HTTP {status}, {detail})",
            file=sys.stderr,
        )
        return False
    return True
