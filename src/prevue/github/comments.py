"""Sticky PR summary comment — marker-based upsert."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from html import escape as escape_html

import requests
from github import GithubException

from prevue.classify.models import CANONICAL_LABEL_ORDER, ClassificationResult, canonical_index
from prevue.dismiss import DismissEntry, render_dismiss_block
from prevue.fingerprint import fingerprint
from prevue.gate import (
    SEVERITY_RANK,
    GateResult,
    severity_counts_line,
    thresholds_line,
    verdict_title,
)
from prevue.github.graphql import GraphQLError, fetch_review_threads, resolve_review_thread
from prevue.github.positions import finding_region_changed
from prevue.models import Finding, ReviewResult

MARKER = "<!-- prevue:sticky -->"
MARKER_WITH_SHA = "<!-- prevue:sticky head={sha} -->"
METADATA_SUMMARY = "<details><summary>Metadata</summary>"
LEGACY_METADATA_HEADING = "### Metadata"
_MARKER_RE = re.compile(r"<!--\s*prevue:sticky(?:\s+head=([0-9a-f]{7,40}))?\s*-->")
INLINE_MARKER = "_posted by Prevue_"
LEGACY_INLINE_MARKER = "<sub>posted by Prevue</sub>"
BOT_LOGINS = {"github-actions[bot]", "github-actions"}

SEVERITY_BADGES = {"error": "🔴", "warning": "🟡", "info": "🔵"}
BADGE_TO_SEVERITY = {badge: sev for sev, badge in SEVERITY_BADGES.items()}
PLACEMENT_BADGES = {
    "inline": "💬 inline",
    "summary-only": "📋 summary-only",
    "position-fallback": "⚠️ position-fallback",
}

# Deterministic disclaimer prepended to the sticky Review section on incremental runs (gap #5).
# This text is a constant — it must not be derived from engine output.
_INCREMENTAL_SCOPE_DISCLAIMER = (
    "> **Incremental review:** This review is scoped to files changed since the last reviewed "
    "commit. Prior open findings on unchanged files are carried forward."
)
_INCREMENTAL_CARRIED_CLAUSE = (
    " {count} prior open finding(s) may be on files outside this incremental diff."
)


def parse_marker_sha(body: str) -> str | None:
    """Extract last-reviewed head SHA from sticky marker body (D-01).

    Returns None for legacy head-less markers or missing markers — caller treats
    that as first-run / full review.
    """
    match = _MARKER_RE.search(body or "")
    return match.group(1) if (match and match.group(1)) else None


def render_marker(head_sha: str) -> str:
    """Render the SHA-bearing sticky marker comment prefix (D-01)."""
    return MARKER_WITH_SHA.format(sha=head_sha)


def parse_severity_from_body(body: str) -> str | None:
    """Recover severity from a live inline comment's leading badge emoji (D-12).

    Anchors to the first non-empty line's leading character(s) only — pattern-match,
    never eval the body. Returns None on no match (fail-safe for human/legacy comments).
    """
    if not body:
        return None
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for badge, severity in BADGE_TO_SEVERITY.items():
            if stripped.startswith(badge):
                return severity
        return None
    return None


_TITLE_FROM_BODY_RE = re.compile(r"^[🔴🟡🔵]\s+\*\*(.+?)\*\*")
# Fallback for legacy inline comments that have a severity badge but no **bold** title
# wrapper (pre-bold-migration). Without this, _is_prevue_inline_comment still detects
# them but _parse_title_from_inline_body returns None, silently dropping them from
# carry-forward on incremental runs.
_TITLE_FROM_BODY_FALLBACK_RE = re.compile(r"^[🔴🟡🔵]\s+(.+?)\s*$")


def _unescape_inline_markdown(value: str) -> str:
    """Reverse _escape_inline_markdown for title re-derivation from live comments."""
    for token in ("`", "*", "_", "[", "]"):
        value = value.replace(f"\\{token}", token)
    return value.replace("\\\\", "\\")


def _parse_title_from_inline_body(body: str) -> str | None:
    """Extract finding title from rendered inline comment first line."""
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _TITLE_FROM_BODY_RE.match(stripped)
        if match:
            return _unescape_inline_markdown(match.group(1))
        fallback = _TITLE_FROM_BODY_FALLBACK_RE.match(stripped)
        if fallback:
            # Legacy badge-only comment: strip any stray bold markers before unescaping.
            return _unescape_inline_markdown(fallback.group(1).strip("* "))
        return None
    return None


@dataclass(frozen=True)
class PriorFinding:
    """Re-derived prior inline finding from live PR comments (D-01/D-12)."""

    path: str
    line: int
    side: str
    title: str
    fingerprint: str
    severity: str | None
    thread_id: str | None


def _log_thread_fetch_failure(context: str, exc: Exception) -> None:
    """Log a thread-fetch failure with enough detail to tell auth/outage from a no-op.

    A bare ``Exception`` log made a misconfigured GITHUB_TOKEN (401/403) or a
    sustained API outage indistinguishable from a PR that simply has no prior
    threads. Surface the HTTP status / GraphQL error type so operators can detect
    degraded lifecycle mode (priors lose thread_id; resolution cannot run).
    """
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        detail = f"HTTP {exc.response.status_code}"
    elif isinstance(exc, GraphQLError):
        detail = "GraphQL errors"
        if isinstance(exc.errors, list) and exc.errors:
            first = exc.errors[0]
            if isinstance(first, dict):
                # GitHub error messages (e.g. "Resource not accessible by integration")
                # are diagnostic, not secret — surface type and message so operators can
                # tell a permission gap from an outage. Truncate to bound log noise.
                err_type = first.get("type")
                message = first.get("message")
                if err_type and message:
                    detail = f"GraphQL {err_type}: {str(message)[:200]}"
                elif err_type:
                    detail = f"GraphQL {err_type}"
                elif message:
                    detail = f"GraphQL: {str(message)[:200]}"
    else:
        detail = type(exc).__name__
    print(
        f"prevue: {context} failed ({detail}); "
        "lifecycle degraded — priors derived without thread_id, resolution skipped",
        file=sys.stderr,
    )


def _thread_id_by_location(threads: list[dict]) -> dict[tuple[str, int, str], str]:
    """Map (path, line, side) → review thread id from GraphQL nodes.

    The ``side`` field comes from the GraphQL ``side`` scalar ("LEFT" or "RIGHT").
    Including side prevents silent last-write-wins collision when two threads exist
    on the same file+line on different diff sides.
    """
    mapping: dict[tuple[str, int, str], str] = {}
    for thread in threads:
        path = thread.get("path")
        line = thread.get("line")
        side = thread.get("side") or "RIGHT"
        thread_id = thread.get("id")
        if path is not None and line is not None and thread_id:
            mapping[(path, line, side)] = thread_id
    return mapping


def _derive_prior_findings_with_threads(
    pr,
    *,
    owner: str | None = None,
    repo: str | None = None,
) -> tuple[list[PriorFinding], list[dict]]:
    """Re-derive prior findings and return the fetched threads alongside them.

    Internal helper so callers that need threads for a second operation (e.g.
    resolve_outdated_prior_findings) can reuse the already-fetched list instead
    of issuing a redundant GraphQL round-trip.
    """
    threads: list[dict] = []
    if owner is not None and repo is not None:
        try:
            threads = fetch_review_threads(owner, repo, pr.number)
        except (GraphQLError, requests.RequestException) as exc:
            _log_thread_fetch_failure("fetch review threads", exc)
    thread_ids = _thread_id_by_location(threads)
    resolved_threads = {t["id"] for t in threads if t.get("isResolved")}

    priors: list[PriorFinding] = []
    for key, comments in _existing_prevue_inline_by_location(pr).items():
        path, line, side = key
        comment = comments[0]
        body = comment.body or ""
        title = _parse_title_from_inline_body(body)
        if title is None:
            continue
        thread_id = thread_ids.get((path, line, side))
        if thread_id is not None and thread_id in resolved_threads:
            # A resolved thread is a closed finding (D-11: open-set is union MINUS
            # resolved). Skip it entirely so a thread resolved by the framework's own
            # resolve_outdated pass, by a maintainer, or on a prior run does not get
            # perpetually re-carried as an open finding. If the issue genuinely still
            # exists the engine re-emits it this run as a fresh current finding.
            continue
        priors.append(
            PriorFinding(
                path=path,
                line=line,
                side=side,
                title=title,
                fingerprint=fingerprint(path, title),
                severity=parse_severity_from_body(body),
                thread_id=thread_id,
            )
        )
    return priors, threads


def derive_prior_findings(
    pr,
    *,
    owner: str | None = None,
    repo: str | None = None,
) -> list[PriorFinding]:
    """Re-derive prior Prevue inline findings from live comments (D-01/D-12)."""
    priors, _threads = _derive_prior_findings_with_threads(pr, owner=owner, repo=repo)
    return priors


def resolve_outdated_prior_findings(
    pr,
    *,
    in_scope_paths: set[str],
    regions_by_path: dict[str, list[tuple[int, int]]],
    current_fingerprints: set[str],
    owner: str,
    repo: str,
    threads: list[dict] | None = None,
    authoritative: bool = False,
) -> set[str]:
    """Resolve outdated review threads conservatively (D-08/D-09).

    Returns fingerprints of priors whose threads were resolved this run.
    Accepts an already-fetched ``threads`` list to avoid a redundant round-trip
    when the caller (run_review) has already fetched threads via derive_prior_findings.
    """
    if threads is None:
        try:
            threads = fetch_review_threads(owner, repo, pr.number)
        except (GraphQLError, requests.RequestException) as exc:
            _log_thread_fetch_failure("fetch review threads for resolve", exc)
            return set()
    resolved_ids = {t["id"] for t in threads if t.get("isResolved")}
    thread_ids = _thread_id_by_location(threads)
    resolved_fps: set[str] = set()

    for key, comments in _existing_prevue_inline_by_location(pr).items():
        path, line, side = key
        if path not in in_scope_paths:
            continue
        body = comments[0].body or ""
        title = _parse_title_from_inline_body(body)
        if title is None:
            continue
        prior_fp = fingerprint(path, title)
        if prior_fp in current_fingerprints:
            continue
        regions = regions_by_path.get(path, [])
        stub = Finding(
            path=path,
            line=line,
            side=side,
            severity=parse_severity_from_body(body) or "info",
            title=title,
            body="",
        )
        if not authoritative and not finding_region_changed(stub, regions):
            continue
        thread_id = thread_ids.get((path, line, side))
        if not thread_id or thread_id in resolved_ids:
            continue
        if resolve_review_thread(thread_id):
            resolved_ids.add(thread_id)
            resolved_fps.add(prior_fp)

    return resolved_fps


def _inline_severity_changed(prior_body: str, new_severity: str) -> bool:
    """True when parseable prior and new severities differ (escalation or de-escalation).

    Returns False when the prior severity cannot be parsed (unknown/legacy badge
    format) — keep the existing comment as-is per D-06 rather than churning it
    unconditionally on every run.
    """
    prior_severity = parse_severity_from_body(prior_body)
    if prior_severity is None:
        return False
    return SEVERITY_RANK[new_severity] != SEVERITY_RANK[prior_severity]


def _safe_suggestion_block(text: str) -> str:
    """Render untrusted suggestion with a fence longer than any backtick run."""
    runs = [len(match.group(0)) for match in re.finditer(r"`+", text)]
    fence_len = max(4, (max(runs) + 1) if runs else 4)
    fence = "`" * fence_len
    return f"{fence}\n{text}\n{fence}"


def _escape_table_cell(value: str) -> str:
    """Escape pipes and collapse newlines for markdown table cells."""
    escaped = value.replace("|", "\\|")
    return escaped.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def _format_finding_location(finding: Finding, placement: str) -> str:
    """Location column/summary — omit bogus line numbers for position-fallback."""
    if placement == "position-fallback":
        return _escape_path_code(finding.path)
    return _escape_location(finding.path, finding.line)


def _escape_location(path: str, line: int) -> str:
    """Escape untrusted location values for markdown code span."""
    safe_path = _escape_table_cell(path).replace("`", "\\`")
    return f"`{safe_path}:{line}`"


def _escape_path_code(path: str) -> str:
    """Escape a file path for use as a markdown inline code span."""
    safe = _escape_table_cell(path).replace("`", "\\`")
    return f"`{safe}`"


def _neutralize_html(text: str) -> str:
    """Encode `<` that starts an HTML-ish token in untrusted/LLM text.

    Covers tags and closing tags (`<tag`, `</tag`) plus comments and declarations/PIs
    (`<!--`, `<?`) so adversarial engine output cannot break out of the `<details>`
    wrappers. Bare `<` followed by whitespace/digits is left as-is to avoid mangling
    prose like "x < 3".
    """
    return re.sub(r"<(?=[/!?a-zA-Z])", "&lt;", text)


def _escape_inline_markdown(value: str) -> str:
    """Escape markdown control chars for short inline title/body snippets."""
    escaped = value.replace("\\", "\\\\")
    for token in ("`", "*", "_", "[", "]"):
        escaped = escaped.replace(token, f"\\{token}")
    return escaped.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def render_inline_comment(finding: Finding) -> str:
    """D-21 uniform inline-comment template from Finding fields."""
    badge = SEVERITY_BADGES[finding.severity]
    # Neutralize HTML before markdown-escaping: inline comments render to all PR
    # viewers, so adversarial engine markup in title/body must not become live HTML.
    parts = [
        f"{badge} **{_escape_inline_markdown(_neutralize_html(finding.title))}**",
        "",
        _escape_inline_markdown(_neutralize_html(finding.body)),
    ]
    if finding.suggestion is not None:
        # Suggestion is NOT HTML-neutralized: it renders inside a code fence (GitHub does
        # not render HTML there), and entity-escaping `<` would corrupt the displayed code.
        # The dynamic-length fence in _safe_suggestion_block prevents fence breakout.
        parts.extend(["", "**Suggested change**", _safe_suggestion_block(finding.suggestion)])
    parts.extend(["", INLINE_MARKER])
    return "\n".join(parts)


def render_findings_table(gate: GateResult) -> str:
    """D-24 severity-grouped findings index — one row per placed finding."""
    if not gate.placed:
        return ""
    rows = [
        "| Severity | Location | Finding | Placement |",
        "| --- | --- | --- | --- |",
    ]
    for placed in gate.placed:
        finding = placed.finding
        badge = SEVERITY_BADGES[finding.severity]
        rows.append(
            "| "
            f"{badge} {finding.severity} | "
            f"{_format_finding_location(finding, placed.placement)} | "
            f"{_escape_table_cell(_neutralize_html(finding.title))} | "
            f"{PLACEMENT_BADGES[placed.placement]} |"
        )
    return "\n".join(rows)


def render_finding_details(gate: GateResult) -> str:
    """D-25 collapsed details for non-inlined findings only."""
    blocks: list[str] = []
    for placed in gate.placed:
        if placed.placement == "inline":
            continue
        finding = placed.finding
        if placed.placement == "position-fallback":
            summary = escape_html(f"{finding.path} — {finding.title}")
        else:
            summary = escape_html(f"{finding.path}:{finding.line} — {finding.title}")
        # Encode any HTML tag sequences in LLM output so they can't escape the <details> wrapper.
        content = _neutralize_html(render_inline_comment(finding))
        blocks.append(f"<details><summary>{summary}</summary>\n\n{content}\n</details>")
    return "\n".join(blocks)


def render_body(
    result: ReviewResult,
    *,
    classification: ClassificationResult | None = None,
    loaded_skills: list[str] | None = None,
    gate: GateResult | None = None,
    classification_disclosure: str | None = None,
    skipped_paths: list[str] | None = None,
    skipped_reason: str | None = None,
    skill_ratios: dict[str, tuple[int, int]] | None = None,
    token_meta: dict[str, object] | None = None,
    reviewed_file_count: int | None = None,
    not_reviewed_file_count: int | None = None,
    cap_skipped: list[str] | None = None,
    head_sha: str | None = None,
    scope: str | None = None,
    carried_open_count: int = 0,
    dismissals: list[DismissEntry] | None = None,
) -> str:
    """Sectioned sticky body: Verdict / Review / Findings / details / Metadata.

    When scope='incremental', the Review section is prefixed with a deterministic
    disclaimer naming the incremental scope and, when carried_open_count > 0,
    that prior open findings exist outside this diff. All other scope values
    (including None/'full') leave the Review section unchanged (engine summary only).
    """
    marker_line = render_marker(head_sha) if head_sha else MARKER
    engine_name = result.engine_meta.get("engine", "unknown")
    model = result.engine_meta.get("model", "unknown")
    duration = result.engine_meta.get("duration_s", "?")
    metadata = f"Engine: {engine_name} · model: {model} · {duration}s"
    if classification is not None:
        if classification.labels:
            ordered_labels = [
                label for label in CANONICAL_LABEL_ORDER if label in classification.labels
            ]
            ordered_labels.extend(
                label for label in classification.labels if label not in set(ordered_labels)
            )
            # The matched value is a trusted glob for rule-matched labels but an
            # untrusted PR path after LLM fallback (review.py sets labels[label] = path).
            # Escape it as an inline code span so backticks/pipes can't break layout.
            labels_line = ", ".join(
                f"{label} (matched {_escape_path_code(classification.labels[label])})"
                for label in ordered_labels
            )
            metadata += f"\nLabels: {labels_line}"
        if classification.bundles:
            bundles_line = ", ".join(sorted(classification.bundles, key=canonical_index))
            metadata += f"\nBundles: {bundles_line}"
        if classification.dropped_count:
            metadata += f"\nFiltered: {classification.dropped_count} filtered"
        if loaded_skills:
            metadata += f"\nSkills: {', '.join(loaded_skills)}"
        else:
            metadata += "\nSkills: none (baseline only)"

    if gate is None:
        verdict_section = "_No verdict in v1 — informational review only._\n\n"
        findings_section = ""
        details_section = ""
    else:
        verdict_section = (
            f"{verdict_title(gate)}\n{severity_counts_line(gate)}\n{thresholds_line(gate)}\n\n"
        )
        findings_section = ""
        if gate.placed or gate.degraded:
            findings_section = f"### Findings\n{render_findings_table(gate)}\n\n"
        details_section = render_finding_details(gate)
        if details_section:
            details_section = f"{details_section}\n\n"
        if gate.placed or gate.dropped_findings:
            metadata += f"\nFindings: {len(gate.placed)} valid · {gate.dropped_findings} dropped"
        if gate.degraded:
            metadata += "\nstructured findings unavailable (parse failure)"
    if classification_disclosure:
        metadata += f"\n{_escape_table_cell(classification_disclosure)}"

    if token_meta:
        review_tokens = token_meta.get("review", 0)
        classify_tokens = token_meta.get("classify", 0)
        # Provenance is per metric: review may be an exact engine count while
        # classify is always a bytes/4 estimate. Fall back to the legacy single
        # "estimated" flag when the caller does not distinguish the two.
        legacy_estimated = token_meta.get("estimated")
        review_est = " ~est" if token_meta.get("review_estimated", legacy_estimated) else ""
        classify_est = " ~est" if token_meta.get("classify_estimated", legacy_estimated) else ""
        token_line = f"Tokens: review{review_est} {review_tokens}"
        if classify_tokens:
            token_line += f" · classify{classify_est} {classify_tokens}"
        metadata += f"\n{token_line}"

    if skill_ratios:
        loaded_total = sum(loaded for loaded, _total in skill_ratios.values())
        skill_total = sum(total for _loaded, total in skill_ratios.values())
        ordered_bundles = sorted(skill_ratios.keys(), key=canonical_index)
        ratio_parts = [
            f"{bundle} {skill_ratios[bundle][0]}/{skill_ratios[bundle][1]}"
            for bundle in ordered_bundles
        ]
        metadata += f"\nSkill coverage: {loaded_total}/{skill_total} loaded — " + " · ".join(
            ratio_parts
        )

    if not_reviewed_file_count and not_reviewed_file_count > 0:
        reviewed = reviewed_file_count or 0
        metadata += (
            f"\nCoverage: classification and skills reflect {reviewed} reviewed file(s) only; "
            f"{not_reviewed_file_count} file(s) not reviewed (over token budget)."
        )

    if cap_skipped:
        # Entries carry their own reason in parens (oversized / symlink guard /
        # missing consumer root), so use a neutral label here rather than "oversized".
        metadata += f"\nConsumer skill notices ({len(cap_skipped)}): " + ", ".join(
            _escape_table_cell(s) for s in cap_skipped
        )

    coverage_section = ""
    if skipped_paths:
        count = len(skipped_paths)
        lines = "\n".join(f"- {_escape_path_code(path)}" for path in skipped_paths)
        # Neutralize HTML so a reason containing </summary> can't break out of the wrapper.
        reason = _neutralize_html(skipped_reason or "over token budget")
        coverage_section = (
            f"### Coverage\n"
            f"**{count} files not reviewed (over token budget)**\n\n"
            f"<details><summary>Skipped files ({count}) — {reason}</summary>\n\n"
            f"{lines}\n</details>\n\n"
        )

    # Build the Review section content: deterministic disclaimer on incremental runs (gap #5).
    review_content = _neutralize_html(result.summary_markdown)
    if scope == "incremental":
        disclaimer = _INCREMENTAL_SCOPE_DISCLAIMER
        if carried_open_count > 0:
            disclaimer += _INCREMENTAL_CARRIED_CLAUSE.format(count=carried_open_count)
        review_content = f"{disclaimer}\n\n{review_content}"

    return (
        f"{marker_line}\n"
        "## Prevue Review\n\n"
        f"### Verdict\n"
        f"{verdict_section}"
        f"### Review\n{review_content}\n\n"
        f"{findings_section}"
        f"{details_section}"
        f"{coverage_section}"
        f"{render_dismiss_block(dismissals) if dismissals else ''}"
        f"{METADATA_SUMMARY}\n\n{metadata}\n</details>\n"
    )


def _is_trusted_sticky_actor(comment) -> bool:
    """Accept only explicitly trusted sticky owners."""
    try:
        user = comment.user
        login = user.login
    except (AttributeError, TypeError):
        return False

    if not isinstance(login, str):
        return False

    # Optional runtime extension for dedicated app identities.
    configured_logins = {
        value.strip()
        for value in os.environ.get("PREVUE_STICKY_OWNER_LOGINS", "").split(",")
        if value.strip()
    }
    return login in (BOT_LOGINS | configured_logins)


def _is_prevue_sticky(comment) -> bool:
    """True for trusted automation comments whose body starts with marker."""
    body = (comment.body or "").lstrip()
    match = _MARKER_RE.search(body)
    if not match or match.start() != 0:
        return False
    return _is_trusted_sticky_actor(comment)


def _upsert_marker_comment(pr, body: str):
    """Create or edit the single bot sticky comment identified by MARKER.

    Re-fetches comments on every call and matches by MARKER, so a retry after a
    GithubException is idempotent: if a prior attempt actually created the comment,
    the retry finds and edits it rather than creating a duplicate.

    Edits the NEWEST sticky (last match) so this stays consistent with
    _read_sticky_body and the workflow preflight when duplicate stickies exist.
    """
    target = None
    for comment in pr.get_issue_comments():
        if _is_prevue_sticky(comment):
            target = comment
    if target is not None:
        target.edit(body)
        return target
    return pr.create_issue_comment(body)


def render_skip_body(*, dropped_count: int | None = None, reason: str | None = None) -> str:
    """Skip sticky body — empty-PR filtered count or explicit skip reason (D-10/D-16)."""
    if reason is not None:
        return f"{MARKER}\n## Prevue Review\n\n{reason}"
    return f"{MARKER}\n## Prevue Review\n\nno reviewable files ({dropped_count} filtered)"


def upsert_skip_note(pr, *, dropped_count: int | None = None, reason: str | None = None):
    """Post idempotent sticky note for empty-PR or bot/label/title skip (D-10/D-16)."""
    return _upsert_marker_comment(pr, render_skip_body(dropped_count=dropped_count, reason=reason))


def upsert_sticky(
    pr,
    result: ReviewResult,
    *,
    classification: ClassificationResult | None = None,
    loaded_skills: list[str] | None = None,
    gate: GateResult | None = None,
    classification_disclosure: str | None = None,
    skipped_paths: list[str] | None = None,
    skipped_reason: str | None = None,
    skill_ratios: dict[str, tuple[int, int]] | None = None,
    token_meta: dict[str, object] | None = None,
    reviewed_file_count: int | None = None,
    not_reviewed_file_count: int | None = None,
    cap_skipped: list[str] | None = None,
    head_sha: str | None = None,
    scope: str | None = None,
    carried_open_count: int = 0,
    dismissals: list[DismissEntry] | None = None,
):
    """Create one sticky comment or edit in place when marker exists (D-06)."""
    body = render_body(
        result,
        classification=classification,
        loaded_skills=loaded_skills,
        gate=gate,
        classification_disclosure=classification_disclosure,
        skipped_paths=skipped_paths,
        skipped_reason=skipped_reason,
        skill_ratios=skill_ratios,
        token_meta=token_meta,
        reviewed_file_count=reviewed_file_count,
        not_reviewed_file_count=not_reviewed_file_count,
        cap_skipped=cap_skipped,
        head_sha=head_sha,
        scope=scope,
        carried_open_count=carried_open_count,
        dismissals=dismissals,
    )
    return _upsert_marker_comment(pr, body)


def _is_prevue_inline_comment(comment) -> bool:
    """True for trusted automation review comments tagged with INLINE_MARKER.

    Backward-compatible: also detects the LEGACY_INLINE_MARKER (HTML sub tag)
    for comments posted before the GFM-safe migration so carry-forward / dedupe /
    resolve on PRs like #23 remain unbroken.
    """
    body = comment.body or ""
    if INLINE_MARKER not in body and LEGACY_INLINE_MARKER not in body:
        return False
    return _is_trusted_sticky_actor(comment)


def inline_location_key(path: str, line: int, side: str | None) -> tuple[str, int, str]:
    """Stable (path, line, side) key for matching/upserting an inline comment.

    Public so review.py can downgrade the exact findings post_inline_review reports
    as failed without duplicating the keying logic (single source of truth)."""
    return (path, line, side or "RIGHT")


def _existing_prevue_inline_by_location(pr) -> dict[tuple[str, int, str], list[object]]:
    """Map (path, line, side) → all existing Prevue inline review comments."""
    existing: dict[tuple[str, int, str], list[object]] = {}
    for comment in pr.get_review_comments():
        if not _is_prevue_inline_comment(comment):
            continue
        # GitHub sets line=None on outdated threads; skip for upsert/prior derive.
        if comment.path is None or comment.line is None:
            continue
        key = inline_location_key(comment.path, comment.line, getattr(comment, "side", None))
        existing.setdefault(key, []).append(comment)
    return existing


def _outdated_prevue_inline_comments(
    pr,
    *,
    in_scope_paths: set[str] | None = None,
) -> list[object]:
    """Prevue inline comments GitHub marked outdated (line is null on REST API)."""
    outdated: list[object] = []
    for comment in pr.get_review_comments():
        if not _is_prevue_inline_comment(comment):
            continue
        if comment.line is not None:
            continue
        path = getattr(comment, "path", None)
        if in_scope_paths is not None and path not in in_scope_paths:
            continue
        outdated.append(comment)
    return outdated


def _delete_prevue_inline_comments(comments: list[object]) -> None:
    """Delete Prevue inline comments (best-effort)."""
    for comment in comments:
        try:
            comment.delete()
        except GithubException as exc:
            status = getattr(exc, "status", "unknown")
            path = getattr(comment, "path", "?")
            line = getattr(comment, "line", "?")
            print(
                f"prevue: stale inline comment delete failed (HTTP {status}, {path}:{line})",
                file=sys.stderr,
            )


def post_inline_review(
    pr,
    gate: GateResult,
    *,
    in_scope_paths: set[str] | None = None,
    regions_by_path: dict[str, list[tuple[int, int]]] | None = None,
    owner: str | None = None,
    repo: str | None = None,
    resolve_outdated: bool = False,
) -> set[tuple[str, int, str]]:
    """Post, update, or remove inline findings — upsert by (path, line, side) on re-run.

    Returns the set of inline location keys that could NOT be represented on the PR
    (edit failed → comment shows stale body; create batch failed → no comment exists).
    An empty set means every inline finding is correctly placed. Callers downgrade only
    the returned keys to summary-only, so partial success is not misreported as a total
    failure (a successfully-posted comment must never be reported as summary-only).
    """
    existing = _existing_prevue_inline_by_location(pr)
    current_keys = {
        inline_location_key(finding.path, finding.line, finding.side) for finding in gate.inline
    }
    stale_comments = [
        comment
        for key, comments in existing.items()
        if key not in current_keys and (in_scope_paths is None or key[0] in in_scope_paths)
        for comment in comments
    ]
    to_delete: list[object] = list(stale_comments)
    to_delete.extend(_outdated_prevue_inline_comments(pr, in_scope_paths=in_scope_paths))

    to_create: list[dict[str, object]] = []
    to_update: list[tuple[object, str, Finding]] = []

    for finding in gate.inline:
        body = render_inline_comment(finding)
        key = inline_location_key(finding.path, finding.line, finding.side)
        prior_comments = existing.get(key, [])
        if prior_comments:
            prior = prior_comments[0]
            if _inline_severity_changed(prior.body or "", finding.severity):
                to_update.append((prior, body, finding))
            if len(prior_comments) > 1:
                to_delete.extend(prior_comments[1:])
            continue
        to_create.append(
            {
                "path": finding.path,
                "line": finding.line,
                "side": finding.side,
                "body": body,
            }
        )

    # Resilient upsert: edit existing first, then create, then ALWAYS attempt
    # stale cleanup. A failure in any phase must not strand stale comments
    # alongside fresh ones — the end state must converge to current findings.
    failed_keys: set[tuple[str, int, str]] = set()
    # Stale comments + any comment whose edit failed: a failed edit leaves the
    # OLD body on the diff while the finding is downgraded to summary-only, so
    # remove it (best-effort) to avoid a misleading authoritative-looking thread.
    for prior, body, finding in to_update:
        try:
            prior.edit(body)
        except GithubException as exc:
            failed_keys.add(inline_location_key(finding.path, finding.line, finding.side))
            to_delete.append(prior)
            status = getattr(exc, "status", "unknown")
            print(
                f"prevue: inline comment update failed "
                f"(HTTP {status}, {finding.path}:{finding.line})",
                file=sys.stderr,
            )

    if to_create:
        count = len(to_create)
        summary_parts = [f"{count} new inline comment(s)"]
        if to_update:
            summary_parts.append(f"{len(to_update)} updated in place")
        body = f"Prevue posted {', '.join(summary_parts)} — see the review summary."

        try:
            pr.create_review(body=body, event="COMMENT", comments=to_create)
        except GithubException as exc:
            failed_keys.update(
                inline_location_key(c["path"], c["line"], c.get("side")) for c in to_create
            )
            status = getattr(exc, "status", "unknown")
            print(
                f"prevue: inline review POST failed (HTTP {status}, {count} comment(s))",
                file=sys.stderr,
            )

    _delete_prevue_inline_comments(to_delete)

    if (
        resolve_outdated
        and in_scope_paths is not None
        and regions_by_path is not None
        and owner is not None
        and repo is not None
    ):
        current_fingerprints = {
            fingerprint(pf.finding.path, pf.finding.title) for pf in gate.placed
        }
        resolve_outdated_prior_findings(
            pr,
            in_scope_paths=in_scope_paths,
            regions_by_path=regions_by_path,
            current_fingerprints=current_fingerprints,
            owner=owner,
            repo=repo,
        )

    return failed_keys
