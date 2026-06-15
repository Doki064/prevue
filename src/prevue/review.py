"""End-to-end review orchestration — fetch → classify → engine → sticky comment."""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

import yaml
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
from prevue.config import load_config, resolve_consumer_config_path
from prevue.engines.base import EngineAdapter
from prevue.engines.prompt import MAX_PROMPT_BYTES, build_prompt, estimate_prompt_overhead_tokens
from prevue.engines.registry import get_adapter
from prevue.engines.tokens import estimate_tokens
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
from prevue.pack import make_file_weight, pack_files, readmit_files, trim_packed_files
from prevue.skills.loader import assemble_instructions, load_skills, select_skills
from prevue.skip import should_skip

BASELINE_INSTRUCTIONS = (
    "You are a senior code reviewer. Review the pull request diff below. "
    "Focus on correctness, security, maintainability, and test coverage. "
    "Be concise and actionable."
)

FORK_UNSUPPORTED_MSG = "Fork PRs are unsupported in v1; skipping review."


def _consumer_skills_root() -> tuple[Path | None, str | None]:
    """Return (skills_dir, rejection_note) — note is set when dir exists but escapes root."""
    consumer_root = os.environ.get("PREVUE_CONSUMER_ROOT")
    if not consumer_root:
        if os.environ.get("GITHUB_ACTIONS"):
            # In Actions, GITHUB_WORKSPACE points to the PR merge ref, not the base ref.
            # Falling back would violate SKIL-04 by loading PR-head consumer skills.
            print(
                "prevue: PREVUE_CONSUMER_ROOT not set; consumer skill loading skipped "
                "(SKIL-04: GITHUB_WORKSPACE may point to PR head, not base ref). "
                "Set PREVUE_CONSUMER_ROOT to the base-ref checkout to load consumer skills.",
                file=sys.stderr,
            )
            return None, (
                "consumer skills skipped — PREVUE_CONSUMER_ROOT not set in Actions "
                "(SKIL-04 base-ref safeguard); built-in skills only"
            )
        consumer_root = os.environ.get("GITHUB_WORKSPACE")
        if not consumer_root:
            return None, None
    root = Path(consumer_root).resolve()
    skills_dir = (root / ".github" / "prevue" / "skills").resolve()
    if not skills_dir.is_dir():
        return None, None
    # Guard against symlinks escaping the consumer root (path traversal / symlink attack).
    if not skills_dir.is_relative_to(root):
        return None, "consumer skills directory ignored (escapes checkout root — symlink guard)"
    return skills_dir, None


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

    consumer_skills_root, skills_root_warn = _consumer_skills_root()

    # Load skills once before packing so builtin overhead is known upfront.
    try:
        skills, cap_skipped = load_skills(
            consumer_skills_root=consumer_skills_root,
            skills_config=config.skills,
            return_skipped=True,
        )
    except (ValidationError, OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        # Malformed frontmatter (ValidationError), unreadable files (OSError), bad
        # encoding (UnicodeDecodeError), or invalid YAML syntax (yaml.YAMLError, raised
        # by frontmatter.loads) all fail closed with a structured failure check rather
        # than crashing the job with no prevue/review signal.
        # Post a stable, class-level message to the public PR; the full exception text
        # (which can include filesystem paths or verbose parser output) goes to stderr only.
        print(f"prevue: consumer skill load failed: {exc!r}", file=sys.stderr)
        reason = (
            f"Could not load a consumer skill file ({type(exc).__name__}). "
            "See the workflow logs for details."
        )
        upsert_skip_note(pr, reason=reason)
        check_published = conclude_skip_check(
            get_repo(ctx),
            diff.head_sha,
            conclusion="failure",
            reason=reason,
            title="review failed",
        )
        if not check_published:
            raise RuntimeError("Failed to publish skill-validation failure check run")
        return

    if skills_root_warn:
        cap_skipped = [skills_root_warn] + cap_skipped

    # Skills are already loaded, so reserve the actual loaded skill tokens (the matched
    # subset that reaches the prompt is ⊆ all loaded) rather than the configured consumer
    # ceiling — an empty/all-capped/all-excluded consumer tree reserves 0, not ~64k tokens,
    # so files are not dropped for headroom that never materializes. The re-admission pass
    # later recovers budget when fewer skills actually match. Count the "## Skill: {name}"
    # header + section join that assemble_instructions adds, not just the raw body.
    loaded_skill_tokens = sum(
        estimate_tokens(f"## Skill: {s.name}\n{s.body.strip()}\n\n") for s in skills
    )
    weight = make_file_weight(ruleset.label_rules, skills=skills)
    available = review_cfg.max_input_tokens - review_cfg.output_reserve_tokens
    overhead = (
        estimate_prompt_overhead_tokens(instructions=BASELINE_INSTRUCTIONS) + loaded_skill_tokens
    )
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

    # Re-admission pass: when actual matched-skill overhead is smaller than the
    # conservative first-pass estimate (all builtins + consumer cap), recover the
    # freed budget and re-admit skipped files in priority order.
    if skipped_files:
        packed_files, skipped_files = readmit_files(
            packed_files,
            skipped_files,
            instructions=instructions,
            available_tokens=available,
            weight=weight,
        )
        skipped_paths = [f.path for f in skipped_files]
        skipped_reason = (
            "Files ranked by classification risk; whole files dropped when over token budget."
            if skipped_paths
            else None
        )
        matched = select_skills(skills, [f.path for f in packed_files])
        skill_ratios = _skill_ratios(skills, matched)
        instructions = assemble_instructions(BASELINE_INSTRUCTIONS, matched)
        # Second trim: re-admitted paths may activate new skills, growing instructions.
        packed_files, trim2_skipped = trim_packed_files(
            packed_files,
            instructions=instructions,
            budget_tokens=available,
            weight=weight,
        )
        if trim2_skipped:
            skipped_files = skipped_files + trim2_skipped
            skipped_paths = [f.path for f in skipped_files]
            skipped_reason = (
                "Files ranked by classification risk; whole files dropped when over token budget."
            )
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

    # Guard against estimate drift BEFORE the LLM classification fallback runs — the
    # final prompt bytes depend only on instructions + packed_files, both finalized
    # above. Checking here avoids spending classify tokens on a prompt we will skip.
    # (bytes/4 token heuristics can undercount non-ASCII content.)
    prompt_probe = ReviewRequest(
        diff=reduced.model_copy(update={"files": packed_files}),
        instructions=instructions,
        budget_seconds=300,
    )
    if len(build_prompt(prompt_probe).encode("utf-8")) > MAX_PROMPT_BYTES:
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
            classify_tokens = estimate_classify_tokens(unmatched_packed)
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

    # Prompt bytes were already validated against MAX_PROMPT_BYTES before classify;
    # instructions and packed_files are unchanged since, so no re-check is needed.
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
            partial=gate.partial,
        )
    engine_tokens = result.engine_meta.get("tokens")
    engine_tokens = engine_tokens if isinstance(engine_tokens, dict) else {}
    sticky_kwargs = {
        "classification": result_cls,
        "loaded_skills": [
            f"{s.name} ({s.bundle})"
            if s.source == "builtin"
            else f"{s.name} ({s.bundle}, consumer)"
            for s in matched
        ],
        "gate": gate,
        "classification_disclosure": classification_disclosure,
        "skipped_paths": skipped_paths,
        "skipped_reason": skipped_reason,
        "skill_ratios": skill_ratios,
        "token_meta": {
            **engine_tokens,
            "classify": classify_tokens,
            # review provenance comes from the engine's own "estimated" flag;
            # classify is always a bytes/4 estimate (estimate_classify_tokens).
            "review_estimated": bool(engine_tokens.get("estimated")),
            "classify_estimated": True,
        },
        "reviewed_file_count": len(packed_files),
        "not_reviewed_file_count": len(skipped_files),
        "cap_skipped": cap_skipped,
    }
    try:
        sticky = upsert_sticky(pr, result, **sticky_kwargs)
    except GithubException as exc:
        print(
            f"prevue: sticky comment upsert failed (HTTP {getattr(exc, 'status', '?')}), retrying",
            file=sys.stderr,
        )
        try:
            sticky = upsert_sticky(pr, result, **sticky_kwargs)
            sticky_failed = False
        except GithubException as retry_exc:
            print(
                f"prevue: sticky retry failed (HTTP {getattr(retry_exc, 'status', '?')})",
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
        skipped_count=len(skipped_files),
    )
    if not check_published:
        raise RuntimeError("Failed to publish review check run")
