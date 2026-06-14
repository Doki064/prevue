"""End-to-end review orchestration — fetch → classify → engine → sticky comment."""

from __future__ import annotations

import os

from prevue.classify.classifier import classify
from prevue.classify.filter import filter_diff
from prevue.classify.llm_fallback import FALLBACK_FAILED_GLOB, FALLBACK_PARTIAL_GLOB, llm_classify
from prevue.classify.models import CANONICAL_LABEL_ORDER, GENERAL_LABEL
from prevue.classify.router import route
from prevue.config import load_config, resolve_consumer_config_path
from prevue.engines.base import EngineAdapter
from prevue.engines.registry import get_adapter
from prevue.gate import GateResult, PlacedFinding, apply_gate
from prevue.github.checks import conclude_review_check, conclude_skip_check
from prevue.github.client import get_authenticated_pull, get_repo, load_pr_context
from prevue.github.comments import (
    _inline_location_key,
    post_inline_review,
    upsert_skip_note,
    upsert_sticky,
)
from prevue.github.diff import fetch_diff
from prevue.github.positions import build_valid_lines
from prevue.models import ReviewRequest
from prevue.skills.loader import assemble_instructions, load_skills, select_skills
from prevue.skip import should_skip

BASELINE_INSTRUCTIONS = (
    "You are a senior code reviewer. Review the pull request diff below. "
    "Focus on correctness, security, maintainability, and test coverage. "
    "Be concise and actionable."
)

FORK_UNSUPPORTED_MSG = "Fork PRs are unsupported in v1; skipping review."


def _inline_key(finding) -> tuple[str, int, str]:
    """Location key matching post_inline_review's failed-key set."""
    return _inline_location_key(finding.path, finding.line, finding.side)


class ForkPrUnsupported(Exception):
    """Raised when head repo differs from base repo (SECR-01)."""

    def __init__(self) -> None:
        super().__init__(FORK_UNSUPPORTED_MSG)


def run_review(*, adapter: EngineAdapter | None = None) -> None:
    """Fetch diff, run engine adapter, post findings, sticky, and check run."""
    ctx = load_pr_context()

    if ctx.head_repo_full != ctx.base_repo_full:
        raise ForkPrUnsupported()

    consumer_path = resolve_consumer_config_path(
        os.environ.get("PREVUE_CONFIG_PATH"),
        consumer_root=os.environ.get("PREVUE_CONSUMER_ROOT"),
    )
    config = load_config(str(consumer_path))
    ruleset = config.ruleset
    review_cfg = config.review
    fallback_cfg = config.fallback

    pr = get_authenticated_pull(ctx)

    skip_reason = should_skip(pr, config.skip)
    if skip_reason:
        upsert_skip_note(pr, reason=skip_reason)
        skip_published = conclude_skip_check(
            get_repo(ctx),
            pr.head.sha,
            conclusion="neutral",
            reason=skip_reason,
        )
        if not skip_published:
            raise RuntimeError("Failed to publish skip check run")
        return

    diff = fetch_diff()
    reduced, dropped = filter_diff(diff, ruleset.ignore_globs)

    if not reduced.files:
        upsert_skip_note(pr, dropped_count=len(dropped))
        skip_published = conclude_skip_check(
            get_repo(ctx), diff.head_sha, dropped_count=len(dropped)
        )
        if not skip_published:
            raise RuntimeError("Failed to publish skip check run")
        return

    engine = adapter or get_adapter(os.environ.get("PREVUE_ENGINE", config.engine))

    result_cls = classify(reduced.files, ruleset.label_rules)
    classification_disclosure: str | None = None
    if fallback_cfg.enabled and result_cls.unmatched:
        fallback_labels, classification_disclosure = llm_classify(
            result_cls.unmatched,
            engine,
            model=fallback_cfg.model,
        )
        for path_or_label, label_or_glob in fallback_labels.items():
            is_degrade_general = path_or_label == GENERAL_LABEL and label_or_glob in {
                FALLBACK_FAILED_GLOB,
                FALLBACK_PARTIAL_GLOB,
            }
            if is_degrade_general:
                result_cls.labels[GENERAL_LABEL] = label_or_glob
                continue
            if (
                isinstance(path_or_label, str)
                and isinstance(label_or_glob, str)
                and label_or_glob in CANONICAL_LABEL_ORDER
                and label_or_glob not in result_cls.labels
            ):
                result_cls.labels[label_or_glob] = path_or_label
        if (
            fallback_labels
            and GENERAL_LABEL in result_cls.labels
            and GENERAL_LABEL not in fallback_labels
            and any(label != GENERAL_LABEL for label in result_cls.labels)
        ):
            result_cls.labels.pop(GENERAL_LABEL, None)

    result_cls.bundles = route(list(result_cls.labels.keys()), ruleset.routing_map)
    result_cls.dropped_count = len(dropped)

    skills = load_skills()
    matched = select_skills(skills, [f.path for f in reduced.files])
    instructions = assemble_instructions(BASELINE_INSTRUCTIONS, matched)

    req = ReviewRequest(
        diff=reduced,
        instructions=instructions,
        budget_seconds=300,
        model=os.environ.get("PREVUE_MODEL", os.environ.get("COPILOT_MODEL")),
    )

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
    failed_inline_keys = post_inline_review(pr, gate)
    if failed_inline_keys and gate.inline:
        downgraded = [
            PlacedFinding(
                finding=placed.finding,
                placement="summary-only"
                if placed.placement == "inline"
                and _inline_key(placed.finding) in failed_inline_keys
                else placed.placement,
            )
            for placed in gate.placed
        ]
        gate = GateResult(
            conclusion=gate.conclusion,
            severity_counts=gate.severity_counts,
            placed=downgraded,
            inline=[
                finding for finding in gate.inline if _inline_key(finding) not in failed_inline_keys
            ],
            config=gate.config,
            degraded=gate.degraded,
            dropped_findings=gate.dropped_findings,
        )
    sticky = upsert_sticky(
        pr,
        result,
        classification=result_cls,
        loaded_skills=[f"{s.name} ({s.bundle})" for s in matched],
        gate=gate,
        classification_disclosure=classification_disclosure,
    )
    check_published = conclude_review_check(
        get_repo(ctx),
        diff.head_sha,
        gate,
        sticky_url=getattr(sticky, "html_url", None),
    )
    if not check_published:
        raise RuntimeError("Failed to publish review check run")
