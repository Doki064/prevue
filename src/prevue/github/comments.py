"""Sticky PR summary comment — marker-based upsert."""

from __future__ import annotations

from prevue.classify.models import CANONICAL_LABEL_ORDER, ClassificationResult, canonical_index
from prevue.models import ReviewResult

MARKER = "<!-- prevue:sticky -->"
BOT_LOGINS = {"github-actions[bot]", "github-actions"}


def render_body(
    result: ReviewResult,
    *,
    classification: ClassificationResult | None = None,
    loaded_skills: list[str] | None = None,
) -> str:
    """Sectioned sticky body: Verdict / Review / Metadata (D-04, D-05)."""
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
            bundles_line = ", ".join(
                sorted(classification.bundles, key=canonical_index)
            )
            metadata += f"\nBundles: {bundles_line}"
        if classification.dropped_count:
            metadata += f"\nFiltered: {classification.dropped_count} filtered"
        if loaded_skills:
            metadata += f"\nSkills: {', '.join(loaded_skills)}"
        elif classification is not None:
            metadata += "\nSkills: none (baseline only)"
    return (
        f"{MARKER}\n"
        "## Prevue Review\n\n"
        "### Verdict\n"
        "_No verdict in v1 — informational review only._\n\n"
        f"### Review\n{result.summary_markdown}\n\n"
        f"### Metadata\n{metadata}\n"
    )


def _is_prevue_sticky(comment) -> bool:
    """True only for bot-authored comments whose body starts with our marker."""
    try:
        login = comment.user.login
    except (AttributeError, TypeError):
        return False
    if login not in BOT_LOGINS:
        return False
    return (comment.body or "").lstrip().startswith(MARKER)


def _upsert_marker_comment(pr, body: str) -> None:
    """Create or edit the single bot sticky comment identified by MARKER."""
    for comment in pr.get_issue_comments():
        if _is_prevue_sticky(comment):
            comment.edit(body)
            return
    pr.create_issue_comment(body)


def render_skip_body(dropped_count: int) -> str:
    """Neutral skip body for all-filtered PRs (D-10)."""
    return f"{MARKER}\n## Prevue Review\n\nno reviewable files ({dropped_count} filtered)"


def upsert_skip_note(pr, dropped_count: int) -> None:
    """Post idempotent sticky note when every file was filtered (D-10)."""
    _upsert_marker_comment(pr, render_skip_body(dropped_count))


def upsert_sticky(
    pr,
    result: ReviewResult,
    *,
    classification: ClassificationResult | None = None,
    loaded_skills: list[str] | None = None,
) -> None:
    """Create one sticky comment or edit in place when marker exists (D-06)."""
    body = render_body(
        result,
        classification=classification,
        loaded_skills=loaded_skills,
    )
    _upsert_marker_comment(pr, body)
