"""End-to-end review orchestration — fetch → classify → engine → sticky comment."""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

from github import GithubException
from pydantic import ValidationError

from prevue.classify.classifier import classify
from prevue.classify.filter import filter_diff
from prevue.classify.llm_fallback import (
    FALLBACK_FAILED_GLOB,
    FALLBACK_PARTIAL_GLOB,
    estimate_classify_tokens,
    llm_classify,
)
from prevue.classify.models import CANONICAL_LABEL_ORDER, GENERAL_LABEL
from prevue.classify.router import route
from prevue.config import SkillsConfig, load_config, resolve_consumer_config_path
from prevue.engines.base import EngineAdapter
from prevue.engines.prompt import estimate_prompt_overhead_tokens
from prevue.engines.registry import get_adapter
from prevue.gate import GateResult, PlacedFinding, apply_gate
from prevue.github.checks import conclude_review_check, conclude_skip_check
from prevue.github.client import get_authenticated_pull, get_repo, load_pr_context
from prevue.github.comments import (
    inline_location_key,
    post_inline_review,
    upsert_skip_note,
    upsert_sticky,
)
from prevue.github.diff import fetch_diff
from prevue.github.positions import build_valid_lines
from prevue.models import ReviewRequest
from prevue.pack import make_file_weight, pack_files, trim_packed_files
from prevue.skills.loader import assemble_instructions, load_skills, select_skills
from prevue.skip import should_skip

BASELINE_INSTRUCTIONS = (
    "You are a senior code reviewer. Review the pull request diff below. "
    "Focus on correctness, security, maintainability, and test coverage. "
    "Be concise and actionable."
)

FORK_UNSUPPORTED_MSG = "Fork PRs are unsupported in v1; skipping review."


def _skill_reserve_tokens(skills_config: SkillsConfig | object) -> int:
    """Conservative consumer skill byte ceiling as tokens (bytes/4)."""
    if isinstance(skills_config, SkillsConfig):
        return skills_config.max_total_consumer_bytes // 4
    return SkillsConfig().max_total_consumer_bytes // 4


def _consumer_skills_root() -> Path | None:
    root_env = os.environ.get("PREVUE_CONSUMER_ROOT") or os.environ.get("GITHUB_WORKSPACE")
    if not root_env:
        return None
    skills_dir = Path(root_env) / ".github" / "prevue" / "skills"
    return skills_dir if skills_dir.is_dir() else None


def _estimate_classify_tokens(paths: list[str]) -> int:
    return estimate_classify_tokens(paths)


def _skill_ratios(all_skills: list, matched: list) -> dict[str, tuple[int, int]]:
    loaded = Counter(s.bundle for s in matched)
    totals = Counter(s.bundle for s in all_skills)
    return {bundle: (loaded[bundle], totals[bundle]) for bundle in totals}


def _inline_key(finding) -> tuple[str, int, str]:
    """Location key matching post_inline_review's failed-key set."""
    return inline_location_key(finding.path, finding.line, finding.side)


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

    # config.engine already encodes PREVUE_ENGINE > prevue.yml > default precedence
    # via _resolve_engine — re-reading the env here would duplicate that rule (WR-06).
    engine = adapter or get_adapter(config.engine)

    classification_disclosure: str | None = None
    classify_tokens = 0

    consumer_skills_root = _consumer_skills_root()
    weight = make_file_weight(ruleset.label_rules)
    available = review_cfg.max_input_tokens - review_cfg.output_reserve_tokens
    skill_reserve = _skill_reserve_tokens(config.skills) if consumer_skills_root is not None else 0
    overhead = estimate_prompt_overhead_tokens(instructions=BASELINE_INSTRUCTIONS) + skill_reserve
    pack_budget = available - overhead if available > overhead else 0
    packed_files, skipped_files = pack_files(
        reduced.files,
        weight=weight,
        budget_tokens=pack_budget,
    )
    skipped_paths = [f.path for f in skipped_files]
    skipped_reason = (
        "Files ranked by classification risk; whole files dropped when over token budget."
        if skipped_paths
        else None
    )

    if not packed_files:
        upsert_skip_note(pr, reason="PR too large to review within budget")
        skip_published = conclude_skip_check(
            get_repo(ctx),
            diff.head_sha,
            conclusion="neutral",
            reason="PR too large to review within budget",
        )
        if not skip_published:
            raise RuntimeError("Failed to publish skip check run")
        return

    try:
        skills, cap_skipped = load_skills(
            consumer_skills_root=consumer_skills_root,
            skills_config=config.skills,
            return_skipped=True,
        )
    except ValidationError as exc:
        reason = f"Invalid consumer skill file: {exc}"
        upsert_skip_note(pr, reason=reason)
        check_published = conclude_skip_check(
            get_repo(ctx),
            diff.head_sha,
            conclusion="failure",
            reason=reason,
        )
        if not check_published:
            raise RuntimeError("Failed to publish skill-validation failure check run")
        return
    matched = select_skills(skills, [f.path for f in packed_files])
    instructions = assemble_instructions(BASELINE_INSTRUCTIONS, matched)
    trimmed, extra_skipped = trim_packed_files(
        packed_files,
        instructions=instructions,
        budget_tokens=available,
        weight=weight,
    )
    if extra_skipped:
        skipped_files = skipped_files + extra_skipped
        skipped_paths = [f.path for f in skipped_files]
        if skipped_paths and not skipped_reason:
            skipped_reason = (
                "Files ranked by classification risk; whole files dropped when over token budget."
            )
    packed_files = trimmed
    matched = select_skills(skills, [f.path for f in packed_files])
    skill_ratios = _skill_ratios(skills, matched)
    instructions = assemble_instructions(BASELINE_INSTRUCTIONS, matched)
    if not packed_files:
        upsert_skip_note(pr, reason="PR too large to review within budget")
        skip_published = conclude_skip_check(
            get_repo(ctx),
            diff.head_sha,
            conclusion="neutral",
            reason="PR too large to review within budget",
        )
        if not skip_published:
            raise RuntimeError("Failed to publish skip check run")
        return

    result_cls = classify(packed_files, ruleset.label_rules)

    unmatched_packed = list(result_cls.unmatched)
    if fallback_cfg.enabled and unmatched_packed:
        fallback_labels, classification_disclosure = llm_classify(
            unmatched_packed,
            engine,
            model=fallback_cfg.model,
        )
        # Only bill classify tokens when classification actually produced usable
        # labels — a fully degraded fallback ({GENERAL_LABEL: FALLBACK_FAILED_GLOB})
        # obtained no real classification, so reporting a non-zero estimate would
        # overstate the audit-trail cost (WR-02).
        produced_real_labels = bool(fallback_labels.keys() - {GENERAL_LABEL})
        if produced_real_labels:
            classify_tokens = _estimate_classify_tokens(unmatched_packed)
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

    packed_diff = reduced.model_copy(update={"files": packed_files})

    req = ReviewRequest(
        diff=packed_diff,
        instructions=instructions,
        budget_seconds=300,
        model=os.environ.get("PREVUE_MODEL", os.environ.get("COPILOT_MODEL")),
    )

    result = engine.review(req)
    result.engine_meta["engine"] = engine.name

    # EngineFailure / CopilotAuthError raise before gate (Phase 1 D-09 red run, no check).
    # Parse degrade flows through gate as neutral (D-04) — distinct failure classes.
    valid_lines = build_valid_lines(packed_files)
    gate = apply_gate(
        result.findings,
        review_cfg,
        valid_lines,
        degraded=result.degraded,
        dropped_findings=result.dropped_findings,
        partial=bool(skipped_files),
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
    engine_tokens = result.engine_meta.get("tokens")
    engine_tokens = engine_tokens if isinstance(engine_tokens, dict) else {}
    try:
        sticky = upsert_sticky(
            pr,
            result,
            classification=result_cls,
            loaded_skills=[
                f"{s.name} ({s.bundle})"
                if s.source == "builtin"
                else f"{s.name} ({s.bundle}, consumer)"
                for s in matched
            ],
            gate=gate,
            classification_disclosure=classification_disclosure,
            skipped_paths=skipped_paths,
            skipped_reason=skipped_reason,
            skill_ratios=skill_ratios,
            token_meta={
                **engine_tokens,
                "classify": classify_tokens,
                # review provenance comes from the engine's own "estimated" flag;
                # classify is always a bytes/4 estimate (estimate_classify_tokens).
                "review_estimated": bool(engine_tokens.get("estimated")),
                "classify_estimated": True,
            },
            reviewed_file_count=len(packed_files),
            not_reviewed_file_count=len(skipped_files),
            cap_skipped=cap_skipped,
        )
    except GithubException as exc:
        print(
            f"prevue: sticky comment upsert failed (HTTP {getattr(exc, 'status', '?')})",
            file=sys.stderr,
        )
        sticky = None
        sticky_failed = True
    else:
        sticky_failed = False
    check_published = conclude_review_check(
        get_repo(ctx),
        diff.head_sha,
        gate,
        sticky_url=getattr(sticky, "html_url", None),
        sticky_failed=sticky_failed,
    )
    if not check_published:
        raise RuntimeError("Failed to publish review check run")
