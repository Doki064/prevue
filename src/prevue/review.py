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
from prevue.dismiss import active_suppressed_fingerprints, parse_dismiss_block
from prevue.engines.base import EngineAdapter
from prevue.engines.prompt import MAX_PROMPT_BYTES, build_prompt, estimate_prompt_overhead_tokens
from prevue.engines.registry import get_adapter
from prevue.engines.tokens import estimate_tokens
from prevue.fingerprint import fingerprint
from prevue.gate import SEVERITY_RANK, GateResult, PlacedFinding, apply_gate
from prevue.github.checks import conclude_review_check, conclude_skip_check
from prevue.github.client import PrContext, get_authenticated_pull, get_repo, load_pr_context
from prevue.github.comments import (
    PriorFinding,
    _derive_prior_findings_with_threads,
    _is_prevue_sticky,
    derive_prior_findings,
    inline_location_key,
    parse_marker_sha,
    post_inline_review,
    resolve_outdated_prior_findings,
    upsert_skip_note,
    upsert_sticky,
)
from prevue.github.diff import (
    decide_scope,
    fetch_diff,
    fetch_diff_in_scope,
    regions_from_comparison,
)
from prevue.github.positions import build_valid_lines, finding_region_changed, regions_changed
from prevue.models import Finding, ReviewRequest, ReviewResult
from prevue.pack import make_file_weight, pack_files, readmit_files, trim_packed_files
from prevue.preflight import resolve_marker_for_scope
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


def _read_sticky_body(pr) -> str | None:
    """Return the newest trusted Prevue sticky comment body, if any.

    Selecting the LAST match (not the first) aligns with the workflow preflight,
    which reads the last bot sticky. If duplicate stickies exist (failed cleanup or
    manual duplication), Python scope/noop decisions then target the same comment
    the preflight inspected, avoiding install-skip vs review-scope divergence.
    """
    newest: str | None = None
    for comment in pr.get_issue_comments():
        if _is_prevue_sticky(comment):
            newest = comment.body or ""
    return newest


def _prior_to_finding(prior: PriorFinding) -> Finding:
    return Finding(
        path=prior.path,
        line=prior.line,
        side=prior.side,  # type: ignore[arg-type]
        severity=prior.severity or "info",  # type: ignore[arg-type]
        title=prior.title,
        body="",
    )


def _dedupe_findings_by_location(findings: list[Finding]) -> list[Finding]:
    """One open-set entry per (path, line, side); keep higher-severity on ties."""
    best: dict[tuple[str, int, str], Finding] = {}
    order: list[tuple[str, int, str]] = []
    for finding in findings:
        key = (finding.path, finding.line, finding.side)
        if key not in best:
            order.append(key)
            best[key] = finding
            continue
        if SEVERITY_RANK[finding.severity] < SEVERITY_RANK[best[key].severity]:
            best[key] = finding
    return [best[key] for key in order]


def _open_set_findings(
    current: list[Finding],
    priors: list[PriorFinding],
    resolved_fingerprints: set[str],
) -> list[Finding]:
    """Union(current, carried-unresolved priors) minus resolved-this-run (D-11).

    Rephrase-at-same-line contract (LIFE-02 / gap #1):
    When a carried prior's (path, line, side) matches a current finding but the
    fingerprints DIFFER (engine rephrased the title), the live inline thread keeps
    the OLD title (D-06 quiet-by-default). The open-set must mirror that — keep the
    carried prior and exclude the current finding(s) at that location so the sticky
    Findings row shows the same title as the live inline comment.

    Exception: severity escalation (warning→error, etc.) at the same location keeps
    the current finding so the gate and inline refresh path can flag the upgrade.
    """
    current_fps = {fingerprint(f.path, f.title) for f in current}
    # Keep the MOST-severe current finding per location (lower SEVERITY_RANK = more
    # severe). A plain dict comprehension is last-write-wins, which could hide a real
    # escalation (e.g. an error after a warning at the same line) behind a less-severe
    # sibling and let the carried prior win instead of the upgrade.
    current_by_loc: dict[tuple[str, int, str], Finding] = {}
    for f in current:
        loc = (f.path, f.line, f.side)
        existing = current_by_loc.get(loc)
        if existing is None or SEVERITY_RANK[f.severity] < SEVERITY_RANK[existing.severity]:
            current_by_loc[loc] = f
    current_locs = set(current_by_loc)
    # Locations (path, line, side) where a carried prior takes precedence over the
    # current engine output (rephrase-at-same-line: live inline unchanged, same
    # (path,line,side) but different fingerprint).
    rephrase_locations: set[tuple[str, int, str]] = set()
    carried: list[Finding] = []
    for prior in priors:
        if prior.fingerprint in resolved_fingerprints or prior.fingerprint in current_fps:
            # True duplicate or resolved: drop the prior (current wins / it's gone).
            continue
        loc = (prior.path, prior.line, prior.side)
        if loc in current_locs:
            current_f = current_by_loc[loc]
            # Unparseable prior severity (None): post_inline_review's _inline_severity_changed
            # declines to refresh the live inline comment, so we must NOT let the current
            # finding win an escalation here either — otherwise the sticky/check would show
            # the upgrade while the PR thread stays on the old comment. Rank it most-severe
            # so `current_rank < prior_rank` is False and the prior is carried (rephrase
            # path), keeping sticky and inline consistent.
            prior_rank = SEVERITY_RANK[prior.severity] if prior.severity is not None else -1
            current_rank = SEVERITY_RANK[current_f.severity]
            if current_rank < prior_rank:
                # Escalation at same line: current wins; inline refresh path applies.
                continue
            if fingerprint(current_f.path, current_f.title) != prior.fingerprint:
                rephrase_locations.add(loc)
        carried.append(_prior_to_finding(prior))
    # Exclude current findings at rephrase-collision locations — the carried prior
    # is already in `carried` and is the authoritative entry for that location.
    filtered_current = [f for f in current if (f.path, f.line, f.side) not in rephrase_locations]
    return _dedupe_findings_by_location(filtered_current + carried)


def _build_known_issues_items(
    priors: list[PriorFinding],
    in_scope_paths: set[str],
    max_n: int,
    *,
    exclude_fingerprints: set[str] | None = None,
) -> list[tuple[str, int, str]]:
    if max_n <= 0:
        return []
    excluded = exclude_fingerprints or set()
    return [
        (prior.path, prior.line, prior.title)
        for prior in priors
        if prior.path in in_scope_paths and prior.fingerprint not in excluded
    ][:max_n]


def _fingerprints_outdated_by_region(
    priors: list[PriorFinding],
    in_scope_paths: set[str],
    regions_by_path: dict[str, list[tuple[int, int]]],
) -> set[str]:
    """Priors whose line region overlaps the incremental delta (candidates for resolve)."""
    outdated: set[str] = set()
    for prior in priors:
        if prior.path not in in_scope_paths:
            continue
        stub = Finding(
            path=prior.path,
            line=prior.line,
            side=prior.side,  # type: ignore[arg-type]
            severity=prior.severity or "info",  # type: ignore[arg-type]
            title=prior.title,
            body="",
        )
        if finding_region_changed(stub, regions_by_path.get(prior.path, [])):
            outdated.add(prior.fingerprint)
    return outdated


def _finish_noop_review(
    pr,
    repo,
    *,
    head_sha: str,
    review_cfg,
    owner: str,
    repo_name: str,
    dismiss_entries,
    scope_label: str | None,
) -> None:
    """Identical re-run: refresh marker/check without engine or resolve (Pitfall 3).

    Re-renders the sticky from the freshly recomputed gate (not just the marker
    prefix) so the visible Verdict/Findings always match the check-run conclusion.
    Skipping the re-render let the two diverge when carried-prior state changed
    between same-SHA runs (e.g. a thread resolved out-of-band drops a finding from
    the recomputed gate while the frozen sticky still showed it).

    Preserves active dismiss suppress-list entries so noop refreshes do not wipe
    maintainer dismiss state or re-open suppressed findings in the gate.
    """
    priors = derive_prior_findings(pr, owner=owner, repo=repo_name)
    open_findings = _open_set_findings([], priors, set())
    suppressed = active_suppressed_fingerprints(dismiss_entries, [], {})
    if suppressed:
        open_findings = [
            finding
            for finding in open_findings
            if fingerprint(finding.path, finding.title) not in suppressed
        ]
    active_dismissals = [entry for entry in dismiss_entries if entry.fingerprint in suppressed]
    # Verdict-only gate: no current diff, so valid_lines is empty and carried priors
    # render as position-fallback in the sticky — correct, they are not on a live hunk.
    gate = apply_gate(
        open_findings,
        review_cfg,
        {},
    )
    noop_result = ReviewResult(
        summary_markdown=(
            "_No changes since the last reviewed commit; carried findings shown below._"
        )
    )
    # One retry on transient GithubException — mirrors the full-review _publish_sticky
    # path so a flaky API call does not leave the marker stale on an otherwise no-op run.
    try:
        sticky = upsert_sticky(
            pr,
            noop_result,
            head_sha=head_sha,
            gate=gate,
            scope=scope_label,
            dismissals=active_dismissals or None,
        )
    except GithubException as exc:
        print(
            f"prevue: noop sticky upsert failed (HTTP {getattr(exc, 'status', '?')}), retrying",
            file=sys.stderr,
        )
        try:
            sticky = upsert_sticky(
                pr,
                noop_result,
                head_sha=head_sha,
                gate=gate,
                scope=scope_label,
                dismissals=active_dismissals or None,
            )
        except GithubException as retry_exc:
            print(
                f"prevue: noop sticky retry failed (HTTP {getattr(retry_exc, 'status', '?')})",
                file=sys.stderr,
            )
            sticky = None
    check_published = conclude_review_check(
        repo,
        head_sha,
        gate,
        sticky_url=getattr(sticky, "html_url", None),
        sticky_failed=sticky is None,
    )
    if not check_published:
        raise RuntimeError("Failed to publish review check run")


class ForkPrUnsupported(Exception):
    """Raised when head repo differs from base repo (SECR-01)."""

    def __init__(self) -> None:
        super().__init__(FORK_UNSUPPORTED_MSG)


def run_review(
    *,
    adapter: EngineAdapter | None = None,
    force_full: bool = False,
    pr_ctx: PrContext | None = None,
) -> None:
    """Fetch diff, run engine adapter, post findings, sticky, and check run."""
    ctx = pr_ctx or load_pr_context()

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

    repo = get_repo(ctx)
    head_sha = pr.head.sha
    owner, repo_name = ctx.repo_full.split("/", 1)
    sticky_body = _read_sticky_body(pr)
    last_sha = parse_marker_sha(sticky_body) if sticky_body else None
    dismiss_entries = parse_dismiss_block(sticky_body)
    marker_for_scope = resolve_marker_for_scope(
        last_sha,
        head_sha,
        incremental=review_cfg.incremental,
        force_full=force_full,
    )
    scope, in_scope_paths, comparison = decide_scope(repo, marker_for_scope, head_sha)

    if scope == "noop":
        _finish_noop_review(
            pr,
            repo,
            head_sha=head_sha,
            review_cfg=review_cfg,
            owner=owner,
            repo_name=repo_name,
            dismiss_entries=dismiss_entries,
            scope_label="incremental" if review_cfg.incremental else None,
        )
        return

    if scope == "incremental" and in_scope_paths is not None:
        diff = fetch_diff_in_scope(in_scope_paths)
    else:
        diff = fetch_diff()
    reduced, dropped = filter_diff(diff, ruleset.ignore_globs)

    if not reduced.files:
        if scope == "incremental":
            _finish_noop_review(
                pr,
                repo,
                head_sha=diff.head_sha,
                review_cfg=review_cfg,
                owner=owner,
                repo_name=repo_name,
                dismiss_entries=dismiss_entries,
                scope_label="incremental",
            )
            return
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

    # Derive priors and known_items early so the byte-limit guard below accounts for
    # the known-issues block that will be added to the actual engine prompt on
    # incremental runs (without this, the guard under-counts on near-limit prompts).
    # _derive_prior_findings_with_threads returns the fetched threads alongside priors
    # so resolve_outdated_prior_findings can reuse them (WR-03: avoid double round-trip).
    reviewed_paths = {f.path for f in packed_files}
    delta_paths = (
        in_scope_paths if scope == "incremental" and in_scope_paths is not None else reviewed_paths
    )
    priors, fetched_threads = _derive_prior_findings_with_threads(pr, owner=owner, repo=repo_name)
    incremental_regions = (
        regions_from_comparison(comparison, delta_paths) if scope == "incremental" else {}
    )
    exclude_from_known = (
        _fingerprints_outdated_by_region(priors, delta_paths, incremental_regions)
        if scope == "incremental"
        else set()
    )
    # Build known-issues from delta_paths (the incremental scope), matching the scope
    # used for exclude_from_known. Using the post-pack reviewed_paths instead would drop
    # priors on in-scope files that packing trimmed, so the same fingerprint could be
    # excluded from outdated-resolution (delta scope) yet absent from dedup guidance.
    known_items = (
        _build_known_issues_items(
            priors,
            delta_paths,
            review_cfg.max_known_issues,
            exclude_fingerprints=exclude_from_known,
        )
        if scope == "incremental"
        else []
    )

    # Guard against estimate drift BEFORE the LLM classification fallback runs — the
    # final prompt bytes depend only on instructions + packed_files + known_items, all
    # finalized above. Checking here avoids spending classify tokens on a prompt we
    # will skip. (bytes/4 token heuristics can undercount non-ASCII content.)
    prompt_probe = ReviewRequest(
        diff=reduced.model_copy(update={"files": packed_files}),
        instructions=instructions,
        budget_seconds=300,
    )
    if (
        len(
            build_prompt(
                prompt_probe,
                known_issues=known_items,
                max_known_issues=review_cfg.max_known_issues,
            ).encode("utf-8")
        )
        > MAX_PROMPT_BYTES
    ):
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
    # Prompt bytes were already validated against MAX_PROMPT_BYTES before classify
    # (including known_items overhead); instructions and packed_files are unchanged
    # since, so no re-check is needed.
    # known_issues/max_known_issues are carried on ReviewRequest so flow.review_with_retry
    # passes them directly to build_prompt — no module-level mutation needed (WR-05).
    req = ReviewRequest(
        diff=packed_diff,
        instructions=instructions,
        budget_seconds=300,
        model=os.environ.get("PREVUE_MODEL", os.environ.get("COPILOT_MODEL")),
        known_issues=known_items,
        max_known_issues=review_cfg.max_known_issues,
    )

    result = engine.review(req)
    result.engine_meta["engine"] = engine.name

    # EngineFailure / CopilotAuthError raise before gate (Phase 1 D-09 red run, no check).
    # Parse degrade flows through gate as neutral (D-04) — distinct failure classes.
    current_fps = {fingerprint(f.path, f.title) for f in result.findings}
    if scope == "incremental" and comparison is not None:
        regions_by_path = regions_from_comparison(comparison, delta_paths)
    else:
        regions_by_path = {f.path: regions_changed(f.path, f.patch) for f in packed_files}
    resolved_fps: set[str] = set()
    if review_cfg.resolve_outdated:
        resolved_fps = resolve_outdated_prior_findings(
            pr,
            in_scope_paths=delta_paths,
            regions_by_path=regions_by_path,
            current_fingerprints=current_fps,
            owner=owner,
            repo=repo_name,
            threads=fetched_threads,  # reuse already-fetched threads (WR-03)
            authoritative=(scope == "full"),
        )

    open_findings = _open_set_findings(result.findings, priors, resolved_fps)
    suppressed = active_suppressed_fingerprints(dismiss_entries, result.findings, regions_by_path)
    if suppressed:
        open_findings = [
            finding
            for finding in open_findings
            if fingerprint(finding.path, finding.title) not in suppressed
        ]
    active_dismissals = [entry for entry in dismiss_entries if entry.fingerprint in suppressed]

    valid_lines = build_valid_lines(packed_files)
    gate = apply_gate(
        open_findings,
        review_cfg,
        valid_lines,
        degraded=result.degraded,
        dropped_findings=result.dropped_findings,
        partial=bool(skipped_files),
    )
    engine_tokens = result.engine_meta.get("tokens")
    engine_tokens = engine_tokens if isinstance(engine_tokens, dict) else {}
    # Findings carried from outside the incremental diff (paths not in this diff's scope).
    carried_open_count = (
        sum(1 for pf in gate.placed if pf.finding.path not in reviewed_paths)
        if scope == "incremental" and reviewed_paths
        else 0
    )
    sticky_base_kwargs = {
        "classification": result_cls,
        "loaded_skills": [
            f"{s.name} ({s.bundle})"
            if s.source == "builtin"
            else f"{s.name} ({s.bundle}, consumer)"
            for s in matched
        ],
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
        "scope": scope if scope in ("incremental", "full") else None,
        "carried_open_count": carried_open_count,
        "dismissals": active_dismissals,
    }

    def _publish_sticky(gate_for_sticky: GateResult) -> tuple[object | None, bool]:
        try:
            sticky_comment = upsert_sticky(
                pr,
                result,
                head_sha=diff.head_sha,
                gate=gate_for_sticky,
                **sticky_base_kwargs,
            )
        except GithubException as exc:
            status = getattr(exc, "status", "?")
            print(
                f"prevue: sticky comment upsert failed (HTTP {status}), retrying",
                file=sys.stderr,
            )
            try:
                sticky_comment = upsert_sticky(
                    pr,
                    result,
                    head_sha=diff.head_sha,
                    gate=gate_for_sticky,
                    **sticky_base_kwargs,
                )
            except GithubException as retry_exc:
                print(
                    f"prevue: sticky retry failed (HTTP {getattr(retry_exc, 'status', '?')})",
                    file=sys.stderr,
                )
                return None, True
            return sticky_comment, False
        return sticky_comment, False

    failed_inline_keys = post_inline_review(
        pr,
        gate,
        in_scope_paths=reviewed_paths,
        regions_by_path=regions_by_path,
        owner=owner,
        repo=repo_name,
        resolve_outdated=False,
    )
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
    sticky, sticky_failed = _publish_sticky(gate)
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
