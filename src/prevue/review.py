"""End-to-end review orchestration — fetch → classify → engine → sticky comment."""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

import yaml
from github import GithubException
from pathspec import GitIgnoreSpec
from pydantic import ValidationError

from prevue.classify.classifier import classify
from prevue.classify.filter import filter_diff
from prevue.classify.llm_fallback import (
    FALLBACK_FAILED_GLOB,
    FALLBACK_PARTIAL_GLOB,
    estimate_classify_tokens,
    llm_classify,
    llm_select_skills,
)
from prevue.classify.models import CANONICAL_LABEL_ORDER, GENERAL_LABEL
from prevue.classify.router import route
from prevue.config import load_config, resolve_consumer_config_path
from prevue.dismiss import active_suppressed_fingerprints, parse_dismiss_block
from prevue.engines.base import EngineAdapter
from prevue.engines.prompt import (
    MAX_PROMPT_BYTES,
    build_prompt,
    build_skill_select_prompt,
    estimate_file_prompt_tokens,
    estimate_prompt_overhead_tokens,
)
from prevue.engines.registry import NonFunctionalEngineError, require_functional_adapter
from prevue.engines.tokens import estimate_tokens
from prevue.fingerprint import fingerprint
from prevue.gate import SEVERITY_RANK, GateResult, PlacedFinding, apply_gate
from prevue.github.checks import conclude_review_check, conclude_skip_check
from prevue.github.client import PrContext, get_authenticated_pull, get_repo, load_pr_context
from prevue.github.comments import (
    PARTIAL_MARKER,
    PriorFinding,
    _derive_prior_findings_with_threads,
    derive_prior_findings,
    inline_location_key,
    parse_marker_sha,
    post_inline_review,
    read_newest_trusted_sticky_body,
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
from prevue.github.positions import (
    build_valid_lines,
    finding_region_changed,
    reconcile_finding_locations,
    regions_changed,
)
from prevue.models import Finding, ReviewRequest, ReviewResult
from prevue.multicall import CallGroup, execute_calls, merge_findings, split_into_calls
from prevue.pack import make_file_weight, pack_files, readmit_files, trim_packed_files
from prevue.preflight import resolve_marker_for_scope
from prevue.skills.loader import assemble_instructions, load_skills
from prevue.skills.selection import (
    KEYWORD_THRESHOLD,
    _dedup_sort,
    _supports_skill_classify,
    keyword_score,
    select_skills_hybrid,
)
from prevue.skip import should_skip

BASELINE_INSTRUCTIONS = (
    "You are a senior code reviewer. Review the pull request diff for correctness, "
    "security, maintainability, and test coverage.\n"
    "- Report every material defect; do not cap, rank away, or omit real issues.\n"
    "- One finding per distinct problem; merge duplicates on the same root cause.\n"
    "- Skip praise, filler, and nitpicks that do not change merge risk.\n"
    "- Prose summary: at most five sentences, findings-first; no file-by-file walkthrough.\n"
    "- When a fix is localized, put example corrected code in suggestion (see output format)."
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


def _refresh_matched(
    packed_files: list,
    skills: list,
    bundles: list[str],
    *,
    adapter,
    llm_skill_names: set[str] | None,
    model: str | None,
    guardrail_keys: list[str] | None = None,
) -> tuple[list, str, list]:
    """Recompute (packed_paths, diff_text, matched) after any pack change.

    Centralizes the repeated pattern:
        packed_paths = [f.path for f in packed_files]
        diff_text = "\\n".join(f.patch or "" for f in packed_files)
        matched = select_skills_hybrid(skills, paths, diff_text, bundles, ...)

    WR-01: ``guardrail_keys`` are ``bundle/filename`` skill keys that must load on
    EVERY call (the documented ``review.guardrail_skills`` security backstop). They
    are force-added to ``matched`` regardless of keyword score or routed bundle, so
    a consumer's always-on security skill is never dropped by selection. Unknown
    keys are ignored (a typo can't fabricate a skill).
    """
    packed_paths = [f.path for f in packed_files]
    diff_text = "\n".join(f.patch or "" for f in packed_files)
    matched = select_skills_hybrid(
        skills,
        packed_paths,
        diff_text,
        bundles,
        adapter=adapter,
        llm_skill_names=llm_skill_names,
        model=model,
    )
    if guardrail_keys:
        wanted = set(guardrail_keys)
        present = {f"{s.bundle}/{s.filename}" for s in matched}
        forced = [
            s
            for s in skills
            if f"{s.bundle}/{s.filename}" in wanted and f"{s.bundle}/{s.filename}" not in present
        ]
        if forced:
            # Re-run the shared dedup/sort so guardrail skills slot into the same
            # canonical (bundle, filename) ordering as keyword/escalation matches.
            matched = _dedup_sort([*matched, *forced])
    return packed_paths, diff_text, matched


def _inline_key(finding) -> tuple[str, int, str]:
    """Location key matching post_inline_review's failed-key set."""
    return inline_location_key(finding.path, finding.line, finding.side)


def _publish_skip(
    pr,
    ctx: PrContext,
    head_sha: str,
    *,
    reason: str | None = None,
    dropped_count: int | None = None,
    conclusion: str = "success",
    title: str | None = None,
) -> None:
    """Post skip sticky + check run; fail closed if check publish fails."""
    skip_kwargs: dict[str, object] = {}
    if reason is not None:
        skip_kwargs["reason"] = reason
    if dropped_count is not None:
        skip_kwargs["dropped_count"] = dropped_count
    upsert_skip_note(pr, **skip_kwargs)
    check_kwargs: dict[str, object] = {}
    if conclusion != "success":
        check_kwargs["conclusion"] = conclusion
    if dropped_count is not None:
        check_kwargs["dropped_count"] = dropped_count
    if reason is not None:
        check_kwargs["reason"] = reason
    if title is not None:
        check_kwargs["title"] = title
    published = conclude_skip_check(get_repo(ctx), head_sha, **check_kwargs)
    if not published:
        raise RuntimeError("Failed to publish skip check run")


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


def _upsert_sticky_with_retry(
    pr,
    result: ReviewResult,
    *,
    head_sha: str,
    gate: GateResult,
    log_prefix: str = "sticky",
    **kwargs: object,
) -> tuple[object | None, bool]:
    try:
        sticky = upsert_sticky(
            pr,
            result,
            head_sha=head_sha,
            gate=gate,
            **kwargs,
        )
    except GithubException as exc:
        print(
            f"prevue: {log_prefix} upsert failed (HTTP {getattr(exc, 'status', '?')}), retrying",
            file=sys.stderr,
        )
        try:
            sticky = upsert_sticky(
                pr,
                result,
                head_sha=head_sha,
                gate=gate,
                **kwargs,
            )
        except GithubException as retry_exc:
            print(
                f"prevue: {log_prefix} retry failed (HTTP {getattr(retry_exc, 'status', '?')})",
                file=sys.stderr,
            )
            return None, True
        return sticky, False
    return sticky, False


_PARTIAL_COVERAGE_MARKERS: tuple[str, ...] = (
    PARTIAL_MARKER,
    "not reviewed (over token budget)",
    "Run token budget reached",
    "run token budget reached",
)


def _prior_review_was_partial(pr) -> bool:
    """True when the newest trusted sticky body discloses skipped-over-budget files.

    Used by the no-op (same-SHA) re-run so a partial prior review cannot be silently
    upgraded to a clean pass (WR-05). Degrades to ``True`` (partial) if the sticky
    cannot be read — fail-closed so a no-op rerun cannot upgrade partial coverage to
    a clean pass.
    """
    try:
        body = read_newest_trusted_sticky_body(pr)
    except Exception:  # noqa: BLE001
        return True  # fail closed: assume partial until sticky is readable
    if not body:
        return False
    return any(marker in body for marker in _PARTIAL_COVERAGE_MARKERS)


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
    """Same-SHA re-run: refresh sticky + check from recomputed gate (Pitfall 3)."""
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
    prior_partial = _prior_review_was_partial(pr)
    gate = apply_gate(
        open_findings,
        review_cfg,
        {},
        partial=prior_partial,
    )
    noop_result = ReviewResult(
        summary_markdown=(
            "_No changes since the last reviewed commit; carried findings shown below._"
        )
    )
    sticky, sticky_failed = _upsert_sticky_with_retry(
        pr,
        noop_result,
        head_sha=head_sha,
        gate=gate,
        scope=scope_label,
        dismissals=active_dismissals or None,
        log_prefix="noop sticky",
        partial_marker=prior_partial,
    )
    check_published = conclude_review_check(
        repo,
        head_sha,
        gate,
        sticky_url=getattr(sticky, "html_url", None),
        sticky_failed=sticky_failed,
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
        _publish_skip(
            pr,
            ctx,
            pr.head.sha,
            reason=skip_reason,
            conclusion="neutral",
        )
        return

    repo = get_repo(ctx)
    head_sha = pr.head.sha
    owner, repo_name = ctx.repo_full.split("/", 1)
    sticky_body = read_newest_trusted_sticky_body(pr)
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
        diff = fetch_diff_in_scope(in_scope_paths, pr=pr)
    else:
        diff = fetch_diff(pr=pr)
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
        _publish_skip(pr, ctx, diff.head_sha, dropped_count=len(dropped))
        return

    # config.engine already encodes PREVUE_ENGINE > prevue.yml > default precedence
    # via _resolve_engine — re-reading the env here would duplicate that rule (WR-06).
    try:
        engine = adapter or require_functional_adapter(config.engine)
    except NonFunctionalEngineError as exc:
        _publish_skip(
            pr,
            ctx,
            diff.head_sha,
            reason=str(exc),
            conclusion="failure",
            title="review failed",
        )
        return

    classification_disclosure: str | None = None
    classify_tokens = 0
    llm_skill_names: set[str] | None = None
    _llm_path_labels: dict[str, str] = {}

    # Classify the full filtered set before packing so dropped files still influence labels.
    result_cls = classify(reduced.files, ruleset.label_rules)

    unmatched_pre_pack = list(result_cls.unmatched)
    if fallback_cfg.enabled and unmatched_pre_pack:
        # LLM fallback on the pre-pack unmatched set.
        fallback_labels, classification_disclosure = llm_classify(
            unmatched_pre_pack,
            engine,
            model=fallback_cfg.model,
        )
        # Only bill classify tokens when classification actually produced usable
        # labels — a fully degraded fallback ({GENERAL_LABEL: FALLBACK_FAILED_GLOB})
        # obtained no real classification, so reporting a non-zero estimate would
        # overstate the audit-trail cost (WR-02).
        produced_real_labels = bool(fallback_labels.keys() - {GENERAL_LABEL})
        if produced_real_labels:
            classify_tokens = estimate_classify_tokens(unmatched_pre_pack)
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

        # Build path→label map for files classified by LLM so _file_bundle_map
        # can assign the correct routed bundle without re-running glob matching.
        _llm_path_labels = {
            p: lbl
            for p, lbl in fallback_labels.items()
            if isinstance(p, str)
            and p != GENERAL_LABEL
            and isinstance(lbl, str)
            and lbl in CANONICAL_LABEL_ORDER
        }
        # Remove successfully LLM-classified paths from unmatched so sticky
        # metadata and disclosure don't report them as unresolved.
        if _llm_path_labels:
            result_cls.unmatched = [p for p in result_cls.unmatched if p not in _llm_path_labels]

    result_cls.bundles = route(list(result_cls.labels.keys()), ruleset.routing_map)
    result_cls.dropped_count = len(dropped)

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
        _publish_skip(
            pr,
            ctx,
            diff.head_sha,
            reason=reason,
            conclusion="failure",
            title="review failed",
        )
        return

    if skills_root_warn:
        cap_skipped = [skills_root_warn] + cap_skipped

    _skill_select_tokens = 0
    if result_cls.bundles and skills and _supports_skill_classify(engine):
        routed_bundle_skills = [s for s in skills if s.bundle in set(result_cls.bundles)]
        if routed_bundle_skills:
            _prefetch_paths = [f.path for f in reduced.files]
            _prefetch_diff = "\n".join(f.patch or "" for f in reduced.files)
            # Split into keyword-matched (deterministic) and escalation candidates
            # (below threshold — need LLM arbitration).  Always materializing
            # _keyword_matched_names means per-pack select_skills_hybrid uses the
            # cached set instead of re-invoking llm_select_skills when a packed
            # subset lowers a skill's score below KEYWORD_THRESHOLD (D-02, WR-10).
            _keyword_matched_names = {
                s.name
                for s in routed_bundle_skills
                if keyword_score(s, _prefetch_paths, _prefetch_diff) >= KEYWORD_THRESHOLD
            }
            _escalation_candidates = [
                s for s in routed_bundle_skills if s.name not in _keyword_matched_names
            ]
            if _escalation_candidates:
                _skill_select_tokens = estimate_tokens(
                    build_skill_select_prompt(_escalation_candidates, ("relevant", "irrelevant"))
                )
                fetched = llm_select_skills(
                    _escalation_candidates,
                    engine,
                    model=(
                        fallback_cfg.model
                        or os.environ.get("PREVUE_MODEL", os.environ.get("COPILOT_MODEL"))
                    ),
                    paths=_prefetch_paths,
                    diff_text=_prefetch_diff,
                )
                # Merge LLM-selected names with keyword-matched names so packing
                # never drops a skill that passed full-diff keyword scoring.
                # None = degraded — pass through all routed skills (D-02 gap-closure).
                llm_skill_names = (
                    fetched | _keyword_matched_names
                    if fetched is not None
                    else {s.name for s in routed_bundle_skills}
                )
            else:
                # All routed skills pass keyword on full diff; cache their names so
                # per-pack calls don't re-invoke llm_select_skills on packed subsets.
                llm_skill_names = _keyword_matched_names

    # Skills are already loaded, so reserve the actual loaded skill tokens (the matched
    # subset that reaches the prompt is ⊆ all loaded) rather than the configured consumer
    # ceiling — an empty/all-capped/all-excluded consumer tree reserves 0, not ~64k tokens,
    # so files are not dropped for headroom that never materializes. The re-admission pass
    # later recovers budget when fewer skills actually match. Count the "## Skill: {name}"
    # header + section join that assemble_instructions adds, not just the raw body.
    loaded_skill_tokens = sum(
        estimate_tokens(f"## Skill: {s.name}\n{s.body.strip()}\n\n") for s in skills
    )
    weight = make_file_weight(
        ruleset.label_rules, skills=skills, path_labels=_llm_path_labels or None
    )
    # Cap effective input at the total reviewable budget across all calls so packing
    # never produces a set that split_into_calls cannot accommodate per-call (D-18).
    effective_input = min(
        review_cfg.max_input_tokens,
        review_cfg.max_tokens_per_call * review_cfg.max_review_calls,
    )
    available = effective_input - review_cfg.output_reserve_tokens
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
        _publish_skip(
            pr,
            ctx,
            diff.head_sha,
            reason="PR too large to review within budget",
            conclusion="neutral",
        )
        return

    _review_model = os.environ.get("PREVUE_MODEL", os.environ.get("COPILOT_MODEL"))
    _hybrid_kwargs: dict = dict(
        skills=skills,
        bundles=result_cls.bundles,
        adapter=engine,
        llm_skill_names=llm_skill_names,
        model=_review_model,
        guardrail_keys=review_cfg.guardrail_skills,
    )

    _, _, matched = _refresh_matched(packed_files, **_hybrid_kwargs)
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
    _, _, matched = _refresh_matched(packed_files, **_hybrid_kwargs)
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
        _, _, matched = _refresh_matched(packed_files, **_hybrid_kwargs)
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
            _, _, matched = _refresh_matched(packed_files, **_hybrid_kwargs)
            skill_ratios = _skill_ratios(skills, matched)
            instructions = assemble_instructions(BASELINE_INSTRUCTIONS, matched)

    if not packed_files:
        _publish_skip(
            pr,
            ctx,
            diff.head_sha,
            reason="PR too large to review within budget",
            conclusion="neutral",
        )
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

    # D-10: Whole-run cap — classify + projected per-call review tokens must fit
    # inside max_total_run_tokens.  Projection = per-file token sum across ALL
    # packed files (conservative: one call per file).  When the budget is exceeded,
    # drop lowest-DIFF-03-priority files and disclose how many were dropped.
    _review_model_str = os.environ.get("PREVUE_MODEL", os.environ.get("COPILOT_MODEL"))
    _run_budget_reached: bool = False
    not_reviewed_run_budget: int = 0
    instruction_overhead_tokens = estimate_prompt_overhead_tokens(instructions=instructions)
    projected_calls = max(1, min(review_cfg.max_review_calls, len(packed_files)))
    projected_review_tokens = projected_calls * instruction_overhead_tokens + sum(
        estimate_file_prompt_tokens(f) for f in packed_files
    )
    whole_run_tokens = classify_tokens + _skill_select_tokens + projected_review_tokens
    if whole_run_tokens > review_cfg.max_total_run_tokens:
        # Reserve instruction overhead for every projected call.
        review_budget_tokens = max(
            0,
            review_cfg.max_total_run_tokens
            - classify_tokens
            - _skill_select_tokens
            - projected_calls * instruction_overhead_tokens,
        )
        # Re-run pack_files with the tighter budget (respects DIFF-03 priority).
        cap_packed, cap_skipped_extra = pack_files(
            packed_files,
            weight=weight,
            budget_tokens=review_budget_tokens,
        )
        run_budget_skipped = cap_skipped_extra
        if not cap_packed:
            skipped_reason = (
                "run token budget reached — all files dropped to fit within "
                "max_total_run_tokens; not reviewed"
            )
            _publish_skip(
                pr,
                ctx,
                diff.head_sha,
                reason=skipped_reason,
                conclusion="neutral",
            )
            return
        # Record files dropped by the whole-run cap (distinct from per-call budget skips)
        skipped_files = skipped_files + run_budget_skipped
        skipped_paths = [f.path for f in skipped_files]
        not_reviewed_run_budget = len(run_budget_skipped)
        _run_budget_reached = True
        skipped_reason = (
            "run token budget reached — lowest-priority files dropped "
            f"({not_reviewed_run_budget} file(s) not reviewed; "
            "run token budget reached)"
        )
        packed_files = cap_packed
        # Refresh matched skills after cap-triggered repack
        _, _, matched = _refresh_matched(packed_files, **_hybrid_kwargs)
        skill_ratios = _skill_ratios(skills, matched)
        instructions = assemble_instructions(BASELINE_INSTRUCTIONS, matched)

    # Build per-file bundle map from classification result for the splitter
    # (file.path → bundle_label derived from per-file glob matching; unmapped → _default_bundle)
    # Build pathspec specs once per active label so we match each file individually
    # rather than assigning all files to the first non-general label (CR-02).
    _label_specs: dict[str, GitIgnoreSpec] = {
        label: GitIgnoreSpec.from_lines(globs)
        for label, globs in ruleset.label_rules.items()
        if label in result_cls.labels and label != GENERAL_LABEL
    }
    _default_bundle = result_cls.bundles[0] if result_cls.bundles else GENERAL_LABEL
    _file_bundle_map: dict[str, str] = {}
    for _f in packed_files:
        if _f.path in _llm_path_labels:
            # File was classified by LLM fallback — use its label's routed bundle.
            _lbl = _llm_path_labels[_f.path]
            _file_bundle_map[_f.path] = ruleset.routing_map.get(_lbl, _lbl)
        else:
            # Iterate in canonical priority order so security beats frontend beats backend …
            for _label in CANONICAL_LABEL_ORDER:
                if _label in _label_specs and _label_specs[_label].check_file(_f.path).include:
                    _file_bundle_map[_f.path] = ruleset.routing_map.get(_label, _label)
                    break
            else:
                _file_bundle_map[_f.path] = _default_bundle

    split_overhead_tokens = estimate_prompt_overhead_tokens(instructions=instructions)
    if review_cfg.max_review_calls > 1 and split_overhead_tokens >= review_cfg.max_tokens_per_call:
        cap_skipped = cap_skipped + [
            (
                f"instruction overhead (~{split_overhead_tokens} tokens, incl. forced "
                f"guardrail skills) >= max_tokens_per_call "
                f"({review_cfg.max_tokens_per_call}); per-call file budget floored to 1 "
                "— multi-call budgeting degraded, final call may exceed the per-call cap"
            )
        ]
    call_groups: list[CallGroup] = split_into_calls(
        packed_files,
        set(result_cls.bundles),
        _file_bundle_map,
        review_cfg,
        instruction_overhead_tokens=split_overhead_tokens,
    )

    # Build per-group ReviewRequests.  When max_review_calls=1, the splitter returns
    # one group containing all packed files → a single request byte-identical to the
    # pre-09-05 path (ENGN-05 single-call default unchanged).
    # known_issues/max_known_issues are carried on ReviewRequest so flow.review_with_retry
    # passes them directly to build_prompt — no module-level mutation needed (WR-05).
    call_requests: list[ReviewRequest] = []
    for group in call_groups:
        group_diff = reduced.model_copy(update={"files": group.files})
        call_requests.append(
            ReviewRequest(
                diff=group_diff,
                instructions=instructions,  # shared instructions (full skill union)
                budget_seconds=300,
                model=_review_model_str,
                known_issues=known_items,
                max_known_issues=review_cfg.max_known_issues,
            )
        )

    # Per-call byte guard: each split call must fit under MAX_PROMPT_BYTES stdin cap.
    # Checking per-call (not monolithic) means multi-call reviews are not falsely skipped
    # when the combined diff would exceed 1 MB but each individual call would not.
    for _call_req in call_requests:
        if (
            len(
                build_prompt(
                    _call_req,
                    known_issues=known_items,
                    max_known_issues=review_cfg.max_known_issues,
                ).encode("utf-8")
            )
            > MAX_PROMPT_BYTES
        ):
            _publish_skip(
                pr,
                ctx,
                diff.head_sha,
                reason="PR too large to review within budget",
                conclusion="neutral",
            )
            return

    # Execute all calls (sequential or parallel) with fail-soft error handling (ENGN-07/D-08).
    # Single-call path (max_review_calls=1): propagate EngineFailure/AuthError directly
    # so existing tests and the D-09 fail-closed contract hold (byte-identical behavior).
    # Multi-call path (≥2 calls): fail-soft — one failing call marks degraded → neutral.
    if len(call_requests) == 1:
        # Single-call: invoke directly so EngineFailure propagates (preserves D-09 contract)
        single_result = engine.review(call_requests[0])
        single_result.engine_meta = {**single_result.engine_meta, "engine": engine.name}
        call_results = [single_result]
        call_failures = 0
    else:
        call_results, call_failures, _failed_call_indices = execute_calls(
            call_requests, engine, concurrency=review_cfg.review_concurrency
        )
        if _failed_call_indices:
            failed_call_files = [
                f
                for idx in _failed_call_indices
                if 0 <= idx < len(call_groups)
                for f in call_groups[idx].files
            ]
            failed_paths = {f.path for f in failed_call_files}
            skipped_files = skipped_files + failed_call_files
            skipped_paths = [f.path for f in skipped_files]
            packed_files = [f for f in packed_files if f.path not in failed_paths]
            reviewed_paths = {f.path for f in packed_files}

    # Merge findings from all calls: fingerprint(path, title) dedup, higher-severity wins (D-08)
    merged_findings = merge_findings(call_results)

    # Aggregate engine metadata across all calls (Pitfall 5: per-call breakdown for 09-06)
    per_call_tokens: list[dict] = []
    total_review_tokens = 0
    any_estimated = False
    all_degraded = False
    all_dropped = 0
    all_summaries: list[str] = []
    for _pos, call_res in enumerate(call_results):
        call_tokens = dict(call_res.engine_meta.get("tokens") or {})
        _ci = call_res.engine_meta.get("call_index", _pos)
        # Attach bundle label so render_body can show "data NNN · security MMM"
        if isinstance(_ci, int) and 0 <= _ci < len(call_groups):
            _grp_bundles = sorted(call_groups[_ci].bundles - {"general"})
            call_tokens["bundle"] = "+".join(_grp_bundles) if _grp_bundles else "call"
        per_call_tokens.append(call_tokens)
        total_review_tokens += call_tokens.get("review", 0)
        if call_tokens.get("estimated"):
            any_estimated = True
        if call_res.degraded:
            all_degraded = True
        all_dropped += call_res.dropped_findings
        all_summaries.append(call_res.summary_markdown)

    # Fail-soft: any call failure degrades the result → neutral conclusion (D-08)
    if call_failures > 0:
        all_degraded = True

    # Build a synthetic ReviewResult so the downstream gate/sticky path is unchanged (D-08)
    # summary_markdown: join per-call summaries (09-06 will render these properly)
    combined_summary = "\n\n".join(s for s in all_summaries if s) or "## Review\n"
    first_meta: dict = call_results[0].engine_meta if call_results else {}
    result = ReviewResult(
        summary_markdown=combined_summary,
        findings=merged_findings,
        degraded=all_degraded,
        dropped_findings=all_dropped,
        engine_meta={
            **first_meta,
            "engine": engine.name,
            "tokens": {
                "review": total_review_tokens,
                **(
                    {"estimated": any_estimated}
                    if any(cr.engine_meta.get("tokens") for cr in call_results)
                    else {}
                ),
            },
            "per_call": per_call_tokens,
        },
    )

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
    open_findings = reconcile_finding_locations(open_findings, valid_lines)
    # Multi-call partial failure must always yield neutral (D-08 fail-soft contract).
    # Parse-degrade (engine returned no parseable findings) also yields neutral.
    # These are distinct: multi-call degraded holds even when surviving calls have findings.
    multi_call_degraded = len(call_requests) > 1 and (
        call_failures > 0 or any(cr.degraded and not cr.findings for cr in call_results)
    )
    parse_degraded = len(call_requests) == 1 and result.degraded and not result.findings
    gate = apply_gate(
        open_findings,
        review_cfg,
        valid_lines,
        degraded=multi_call_degraded or parse_degraded,
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
    # D-11: skill selection provenance for sticky metadata.
    _final_packed_paths = [f.path for f in packed_files]
    _final_diff_text = "\n".join(f.patch or "" for f in packed_files)

    def _render_skill_entry(s) -> str:
        if s.source == "builtin":
            return f"{s.name} ({s.bundle})"
        return f"{s.name} ({s.bundle}, consumer)"

    _loaded_skills: list[str] = []
    _skill_sources: dict[str, str] = {}
    for _skill in matched:
        _entry = _render_skill_entry(_skill)
        _loaded_skills.append(_entry)
        _score = keyword_score(_skill, _final_packed_paths, _final_diff_text)
        if _score >= KEYWORD_THRESHOLD:
            _skill_sources[_entry] = "keyword"
        elif llm_skill_names and _skill.name in llm_skill_names:
            _skill_sources[_entry] = "llm"
        else:
            _skill_sources[_entry] = "routed"

    sticky_base_kwargs = {
        "classification": result_cls,
        "loaded_skills": _loaded_skills,
        "skill_sources": _skill_sources or None,
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
            "per_call": result.engine_meta.get("per_call", []),
        },
        "reviewed_file_count": len(packed_files),
        "not_reviewed_file_count": len(skipped_files),
        "cap_skipped": cap_skipped,
        "scope": scope if scope in ("incremental", "full") else None,
        "carried_open_count": carried_open_count,
        "dismissals": active_dismissals,
        "run_budget_reached": _run_budget_reached,
        "run_budget_skipped_count": not_reviewed_run_budget,
        "partial_marker": gate.partial,
    }

    # Post sticky first so the summary appears before inline comments in the PR timeline.
    sticky, sticky_failed = _upsert_sticky_with_retry(
        pr,
        result,
        head_sha=diff.head_sha,
        gate=gate,
        **sticky_base_kwargs,
    )

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
        # Re-upsert to reflect the downgraded placements caused by inline post failures.
        sticky, sticky_failed = _upsert_sticky_with_retry(
            pr,
            result,
            head_sha=diff.head_sha,
            gate=gate,
            **sticky_base_kwargs,
        )
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
