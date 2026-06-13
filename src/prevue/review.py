"""End-to-end review orchestration — fetch → classify → engine → sticky comment."""

from __future__ import annotations

import os

from prevue.classify.classifier import classify
from prevue.classify.filter import filter_diff
from prevue.classify.router import route
from prevue.classify.rules import load_ruleset
from prevue.engines.base import EngineAdapter
from prevue.engines.copilot_cli import CopilotCliAdapter
from prevue.gate import apply_gate, load_review_config
from prevue.github.checks import conclude_review_check, conclude_skip_check
from prevue.github.client import get_authenticated_pull, get_repo, load_pr_context
from prevue.github.comments import post_inline_review, upsert_skip_note, upsert_sticky
from prevue.github.diff import fetch_diff
from prevue.github.positions import build_valid_lines
from prevue.models import ReviewRequest
from prevue.skills.loader import assemble_instructions, load_skills, select_skills

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
    """Fetch diff, run engine adapter, post findings, sticky, and check run."""
    ctx = load_pr_context()

    if ctx.head_repo_full != ctx.base_repo_full:
        raise ForkPrUnsupported()

    ruleset = load_ruleset()
    review_cfg = load_review_config()

    diff = fetch_diff()
    reduced, dropped = filter_diff(diff, ruleset.ignore_globs)
    pr = get_authenticated_pull(ctx)

    if not reduced.files:
        upsert_skip_note(pr, dropped_count=len(dropped))
        conclude_skip_check(get_repo(ctx), diff.head_sha, dropped_count=len(dropped))
        return

    result_cls = classify(reduced.files, ruleset.label_rules)
    result_cls.bundles = route(list(result_cls.labels.keys()), ruleset.routing_map)
    result_cls.dropped_count = len(dropped)

    skills = load_skills()
    matched = select_skills(skills, [f.path for f in reduced.files])
    instructions = assemble_instructions(BASELINE_INSTRUCTIONS, matched)

    req = ReviewRequest(
        diff=reduced,
        instructions=instructions,
        budget_seconds=300,
        model=os.environ.get("COPILOT_MODEL"),
    )

    engine = adapter or CopilotCliAdapter()
    result = engine.review(req)

    # EngineFailure / CopilotAuthError raise before gate (Phase 1 D-09 red run, no check).
    # Parse degrade flows through gate as neutral (D-04) — distinct failure classes.
    valid_lines = build_valid_lines(reduced.files)
    gate = apply_gate(
        result.findings,
        review_cfg,
        valid_lines,
        degraded=result.degraded,
        dropped_findings=result.dropped_findings,
    )
    post_inline_review(pr, gate)  # return value ignored in v1 (04-04)
    sticky = upsert_sticky(
        pr,
        result,
        classification=result_cls,
        loaded_skills=[f"{s.name} ({s.bundle})" for s in matched],
        gate=gate,
    )
    conclude_review_check(
        get_repo(ctx),
        diff.head_sha,
        gate,
        sticky_url=getattr(sticky, "html_url", None),
    )
