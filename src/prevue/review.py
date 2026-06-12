"""End-to-end review orchestration — fetch → classify → engine → sticky comment."""

from __future__ import annotations

import os

from prevue.classify.classifier import classify
from prevue.classify.filter import filter_diff
from prevue.classify.router import route
from prevue.classify.rules import load_ruleset
from prevue.engines.base import EngineAdapter
from prevue.engines.copilot_cli import CopilotCliAdapter
from prevue.github.client import get_authenticated_pull, load_pr_context
from prevue.github.comments import upsert_sticky
from prevue.github.diff import fetch_diff
from prevue.models import ReviewRequest

BASELINE_INSTRUCTIONS = (
    "You are a senior code reviewer. Review the pull request diff below. "
    "Focus on correctness, security, maintainability, and test coverage. "
    "Be concise and actionable."
)

FORK_UNSUPPORTED_MSG = "Fork PRs are unsupported in v1; skipping review."


class ForkPrUnsupported(Exception):
    """Raised when head repo differs from base repo (SECR-01)."""

    def __init__(self) -> None:
        super().__init__(FORK_UNSUPPORTED_MSG)


def run_review(*, adapter: EngineAdapter | None = None) -> None:
    """Fetch diff, run engine adapter, upsert sticky comment on success."""
    ctx = load_pr_context()

    if ctx.head_repo_full != ctx.base_repo_full:
        raise ForkPrUnsupported()

    diff = fetch_diff()
    # Plan 03: D-10 empty-PR neutral skip
    ruleset = load_ruleset()
    reduced, dropped = filter_diff(diff, ruleset.ignore_globs)
    result_cls = classify(reduced.files, ruleset.label_rules)
    result_cls.bundles = route(list(result_cls.labels.keys()), ruleset.routing_map)
    result_cls.dropped_count = len(dropped)

    req = ReviewRequest(
        diff=reduced,
        instructions=BASELINE_INSTRUCTIONS,
        budget_seconds=300,
        model=os.environ.get("COPILOT_MODEL"),
    )

    engine = adapter or CopilotCliAdapter()
    result = engine.review(req)

    pr = get_authenticated_pull(ctx)
    upsert_sticky(pr, result, classification=result_cls)
