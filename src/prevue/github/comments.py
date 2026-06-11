"""Sticky PR summary comment — marker-based upsert."""

from __future__ import annotations

from prevue.models import ReviewResult

MARKER = "<!-- prevue:sticky -->"
BOT_LOGINS = {"github-actions[bot]", "github-actions"}


def render_body(result: ReviewResult) -> str:
    """Sectioned sticky body: Verdict / Review / Metadata (D-04, D-05)."""
    model = result.engine_meta.get("model", "unknown")
    duration = result.engine_meta.get("duration_s", "?")
    return (
        f"{MARKER}\n"
        "## Prevue Review\n\n"
        "### Verdict\n"
        "_No verdict in v1 — informational review only._\n\n"
        f"### Review\n{result.summary_markdown}\n\n"
        f"### Metadata\nEngine: copilot-cli · model: {model} · {duration}s\n"
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


def upsert_sticky(pr, result: ReviewResult) -> None:
    """Create one sticky comment or edit in place when marker exists (D-06)."""
    body = render_body(result)
    for comment in pr.get_issue_comments():
        if _is_prevue_sticky(comment):
            comment.edit(body)
            return
    pr.create_issue_comment(body)
