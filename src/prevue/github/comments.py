"""Sticky PR summary comment — marker-based upsert."""

from __future__ import annotations

import os
import re
import sys
from html import escape as escape_html

from github import GithubException

from prevue.classify.models import CANONICAL_LABEL_ORDER, ClassificationResult, canonical_index
from prevue.gate import GateResult, severity_counts_line, thresholds_line, verdict_title
from prevue.models import Finding, ReviewResult

MARKER = "<!-- prevue:sticky -->"
INLINE_MARKER = "<sub>posted by Prevue</sub>"
BOT_LOGINS = {"github-actions[bot]", "github-actions"}

SEVERITY_BADGES = {"error": "🔴", "warning": "🟡", "info": "🔵"}
PLACEMENT_BADGES = {
    "inline": "💬 inline",
    "summary-only": "📋 summary-only",
    "position-fallback": "⚠️ position-fallback",
}


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


def _escape_location(path: str, line: int) -> str:
    """Escape untrusted location values for markdown code span."""
    safe_path = _escape_table_cell(path).replace("`", "\\`")
    return f"`{safe_path}:{line}`"


def _escape_path_code(path: str) -> str:
    """Escape a file path for use as a markdown inline code span."""
    safe = _escape_table_cell(path).replace("`", "\\`")
    return f"`{safe}`"


def _escape_inline_markdown(value: str) -> str:
    """Escape markdown control chars for short inline title/body snippets."""
    escaped = value.replace("\\", "\\\\")
    for token in ("`", "*", "_", "[", "]"):
        escaped = escaped.replace(token, f"\\{token}")
    return escaped.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def render_inline_comment(finding: Finding) -> str:
    """D-21 uniform inline-comment template from Finding fields."""
    badge = SEVERITY_BADGES[finding.severity]
    parts = [
        f"{badge} **{_escape_inline_markdown(finding.title)}**",
        "",
        _escape_inline_markdown(finding.body),
    ]
    if finding.suggestion is not None:
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
            f"{_escape_location(finding.path, finding.line)} | "
            f"{_escape_table_cell(finding.title)} | "
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
        summary = escape_html(f"{finding.path}:{finding.line} — {finding.title}")
        # Sanitize closing tags that could escape the <details> wrapper (adversarial LLM output).
        content = render_inline_comment(finding).replace("</details>", "&lt;/details&gt;")
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
) -> str:
    """Sectioned sticky body: Verdict / Review / Findings / details / Metadata."""
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
            labels_line = ", ".join(
                f"{label} (matched `{classification.labels[label]}`)" for label in ordered_labels
            )
            metadata += f"\nLabels: {labels_line}"
        if classification.bundles:
            bundles_line = ", ".join(sorted(classification.bundles, key=canonical_index))
            metadata += f"\nBundles: {bundles_line}"
        if classification.dropped_count:
            metadata += f"\nFiltered: {classification.dropped_count} filtered"
        if loaded_skills:
            metadata += f"\nSkills: {', '.join(loaded_skills)}"
        elif classification is not None:
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
        metadata += f"\nSkipped {len(cap_skipped)} oversized consumer skill(s): " + ", ".join(
            _escape_table_cell(s) for s in cap_skipped
        )

    coverage_section = ""
    if skipped_paths:
        count = len(skipped_paths)
        lines = "\n".join(f"- {_escape_path_code(path)}" for path in skipped_paths)
        reason = skipped_reason or "over token budget"
        coverage_section = (
            f"### Coverage\n"
            f"**{count} files not reviewed (over token budget)**\n\n"
            f"<details><summary>Skipped files ({count}) — {reason}</summary>\n\n"
            f"{lines}\n</details>\n\n"
        )

    return (
        f"{MARKER}\n"
        "## Prevue Review\n\n"
        f"### Verdict\n"
        f"{verdict_section}"
        f"### Review\n{result.summary_markdown}\n\n"
        f"{findings_section}"
        f"{details_section}"
        f"{coverage_section}"
        f"### Metadata\n{metadata}\n"
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
    if not (comment.body or "").lstrip().startswith(MARKER):
        return False
    return _is_trusted_sticky_actor(comment)


def _upsert_marker_comment(pr, body: str):
    """Create or edit the single bot sticky comment identified by MARKER."""
    for comment in pr.get_issue_comments():
        if _is_prevue_sticky(comment):
            comment.edit(body)
            return comment
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
    )
    return _upsert_marker_comment(pr, body)


def _is_prevue_inline_comment(comment) -> bool:
    """True for trusted automation review comments tagged with INLINE_MARKER."""
    if INLINE_MARKER not in (comment.body or ""):
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
        key = inline_location_key(comment.path, comment.line, getattr(comment, "side", None))
        existing.setdefault(key, []).append(comment)
    return existing


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


def post_inline_review(pr, gate: GateResult) -> set[tuple[str, int, str]]:
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
        if key not in current_keys
        for comment in comments
    ]
    to_delete: list[object] = list(stale_comments)

    to_create: list[dict[str, object]] = []
    to_update: list[tuple[object, str, Finding]] = []

    for finding in gate.inline:
        body = render_inline_comment(finding)
        key = inline_location_key(finding.path, finding.line, finding.side)
        prior_comments = existing.get(key, [])
        if prior_comments:
            to_update.append((prior_comments[0], body, finding))
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
    return failed_keys
