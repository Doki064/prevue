"""Sticky PR summary comment — marker-based upsert."""

from __future__ import annotations

from prevue.classify.models import CANONICAL_LABEL_ORDER, ClassificationResult
from prevue.models import ReviewResult

MARKER = "<!-- prevue:sticky -->"
BOT_LOGINS = {"github-actions[bot]", "github-actions"}


def _canonical_index(name: str) -> int:
    try:
        return CANONICAL_LABEL_ORDER.index(name)
    except ValueError:
        return len(CANONICAL_LABEL_ORDER)


def render_body(
    result: ReviewResult,
    *,
    classification: ClassificationResult | None = None,
) -> str:
    """Sectioned sticky body: Verdict / Review / Metadata (D-04, D-05)."""
    model = result.engine_meta.get("model", "unknown")
    duration = result.engine_meta.get("duration_s", "?")
    metadata = f"Engine: copilot-cli · model: {model} · {duration}s"
    if classification is not None:
        if classification.labels:
            labels_line = ", ".join(
                f"{label} (matched `{classification.labels[label]}`)"
                for label in CANONICAL_LABEL_ORDER
                if label in classification.labels
            )
            metadata += f"\nLabels: {labels_line}"
        if classification.bundles:
            bundles_line = ", ".join(
                sorted(classification.bundles, key=_canonical_index)
            )
            metadata += f"\nBundles: {bundles_line}"
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


def upsert_sticky(
    pr,
    result: ReviewResult,
    *,
    classification: ClassificationResult | None = None,
) -> None:
    """Create one sticky comment or edit in place when marker exists (D-06)."""
    body = render_body(result, classification=classification)
    for comment in pr.get_issue_comments():
        if _is_prevue_sticky(comment):
            comment.edit(body)
            return
    pr.create_issue_comment(body)
