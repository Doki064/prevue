"""Sticky PR summary comment — marker-based upsert."""

from __future__ import annotations

import os
import re
import sys

from github import GithubException

from prevue.classify.models import CANONICAL_LABEL_ORDER, ClassificationResult, canonical_index
from prevue.gate import GateResult, severity_counts_line, thresholds_line, verdict_title
from prevue.models import Finding, ReviewResult

MARKER = "<!-- prevue:sticky -->"
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
    parts.extend(["", "<sub>posted by Prevue</sub>"])
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
            f"`{finding.path}:{finding.line}` | "
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
        summary = f"{finding.path}:{finding.line} — {_escape_table_cell(finding.title)}"
        blocks.append(
            f"<details><summary>{summary}</summary>\n\n{render_inline_comment(finding)}\n</details>"
        )
    return "\n".join(blocks)


def render_body(
    result: ReviewResult,
    *,
    classification: ClassificationResult | None = None,
    loaded_skills: list[str] | None = None,
    gate: GateResult | None = None,
) -> str:
    """Sectioned sticky body: Verdict / Review / Findings / details / Metadata."""
    model = result.engine_meta.get("model", "unknown")
    duration = result.engine_meta.get("duration_s", "?")
    metadata = f"Engine: copilot-cli · model: {model} · {duration}s"
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
        metadata += f"\n{thresholds_line(gate)}"

    return (
        f"{MARKER}\n"
        "## Prevue Review\n\n"
        f"### Verdict\n"
        f"{verdict_section}"
        f"### Review\n{result.summary_markdown}\n\n"
        f"{findings_section}"
        f"{details_section}"
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


def render_skip_body(dropped_count: int) -> str:
    """Neutral skip body for all-filtered PRs (D-10)."""
    return f"{MARKER}\n## Prevue Review\n\nno reviewable files ({dropped_count} filtered)"


def upsert_skip_note(pr, dropped_count: int):
    """Post idempotent sticky note when every file was filtered (D-10)."""
    return _upsert_marker_comment(pr, render_skip_body(dropped_count))


def upsert_sticky(
    pr,
    result: ReviewResult,
    *,
    classification: ClassificationResult | None = None,
    loaded_skills: list[str] | None = None,
    gate: GateResult | None = None,
):
    """Create one sticky comment or edit in place when marker exists (D-06)."""
    body = render_body(
        result,
        classification=classification,
        loaded_skills=loaded_skills,
        gate=gate,
    )
    return _upsert_marker_comment(pr, body)


def post_inline_review(pr, gate: GateResult) -> bool:
    """Post one batched COMMENT review for inline findings (D-20)."""
    if not gate.inline:
        return True

    comments = [
        {
            "path": finding.path,
            "line": finding.line,
            "side": finding.side,
            "body": render_inline_comment(finding),
        }
        for finding in gate.inline
    ]
    count = len(comments)
    body = f"Prevue posted {count} inline comment(s) — see the review summary."

    try:
        # Default commit_id is safe: concurrency group cancels superseded runs.
        pr.create_review(body=body, event="COMMENT", comments=comments)
    except GithubException as exc:
        status = getattr(exc, "status", "unknown")
        print(
            f"prevue: inline review POST failed (HTTP {status}, {count} comment(s))",
            file=sys.stderr,
        )
        return False
    return True
