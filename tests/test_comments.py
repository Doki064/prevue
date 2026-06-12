"""Tests for sticky PR comment upsert."""

from __future__ import annotations

from unittest.mock import MagicMock

from prevue.classify.models import ClassificationResult
from prevue.github.comments import (
    BOT_LOGINS,
    MARKER,
    _is_prevue_sticky,
    render_body,
    upsert_sticky,
)
from prevue.models import ReviewResult


def _sample_result() -> ReviewResult:
    return ReviewResult(
        summary_markdown="## Canned review\n\nNo issues found.",
        findings=[],
        engine_meta={"model": "fake", "duration_s": 0.1},
    )


def test_render_body_contains_marker_and_sections() -> None:
    body = render_body(_sample_result())

    assert body.startswith(MARKER)
    assert "## Prevue Review" in body
    assert "### Verdict" in body
    assert "no verdict in v1" in body.lower()
    assert "### Review" in body
    assert "## Canned review" in body
    assert "### Metadata" in body
    assert "fake" in body
    assert "0.1" in body


def test_render_body_metadata_shows_labels_and_matched_globs() -> None:
    classification = ClassificationResult(
        labels={"frontend": "**/*.tsx"},
        bundles=["frontend"],
    )
    body = render_body(_sample_result(), classification=classification)

    assert "### Metadata" in body
    assert "frontend" in body
    assert "**/*.tsx" in body
    assert "Bundles:" in body


def test_render_body_metadata_canonical_label_order() -> None:
    """Pitfall 5: Metadata renders labels in CANONICAL_LABEL_ORDER, not alphabetical."""
    classification = ClassificationResult(
        labels={"infra": "**/*.tf", "security": "**/.env*"},
        bundles=["infra", "security"],
    )
    body = render_body(_sample_result(), classification=classification)

    labels_section = body.split("Labels: ", 1)[1].split("\nBundles:", 1)[0]
    assert labels_section.index("security") < labels_section.index("infra")
    bundles_section = body.split("Bundles: ", 1)[1].split("\n", 1)[0]
    assert bundles_section.index("security") < bundles_section.index("infra")


def test_upsert_sticky_creates_when_no_marker() -> None:
    pr = MagicMock()
    pr.get_issue_comments.return_value = []

    upsert_sticky(pr, _sample_result())

    pr.create_issue_comment.assert_called_once()
    body = pr.create_issue_comment.call_args[0][0]
    assert MARKER in body


def test_upsert_sticky_edits_existing_marker_comment() -> None:
    existing = MagicMock()
    existing.body = f"{MARKER}\nold content"
    existing.user.login = "github-actions[bot]"
    assert existing.user.login in BOT_LOGINS

    pr = MagicMock()
    pr.get_issue_comments.return_value = [existing]

    upsert_sticky(pr, _sample_result())

    existing.edit.assert_called_once()
    pr.create_issue_comment.assert_not_called()
    body = existing.edit.call_args[0][0]
    assert MARKER in body
    assert "no verdict in v1" in body.lower()


def test_upsert_sticky_skips_non_marker_comments() -> None:
    other = MagicMock()
    other.body = "Unrelated bot comment"
    other.user.login = "github-actions[bot]"

    pr = MagicMock()
    pr.get_issue_comments.return_value = [other]

    upsert_sticky(pr, _sample_result())

    other.edit.assert_not_called()
    pr.create_issue_comment.assert_called_once()


def test_upsert_sticky_skips_human_comment_with_marker_substring() -> None:
    """Marker buried in human text must not be edited — avoids hijack/duplicate."""
    human = MagicMock()
    human.body = f"Quoting Prevue output:\n{MARKER}\nnot our sticky"
    human.user.login = "human-reviewer"

    pr = MagicMock()
    pr.get_issue_comments.return_value = [human]

    upsert_sticky(pr, _sample_result())

    human.edit.assert_not_called()
    pr.create_issue_comment.assert_called_once()


def test_is_prevue_sticky_false_on_malformed_user() -> None:
    comment = MagicMock()
    comment.user = None
    comment.body = f"{MARKER}\nsticky"
    assert _is_prevue_sticky(comment) is False

    comment.user = "not-an-object"
    assert _is_prevue_sticky(comment) is False


def test_upsert_sticky_creates_when_comment_user_malformed() -> None:
    """Malformed comment objects must not crash upsert — create fresh sticky instead."""
    broken = MagicMock()
    broken.body = f"{MARKER}\nold"
    broken.user = None

    pr = MagicMock()
    pr.get_issue_comments.return_value = [broken]

    upsert_sticky(pr, _sample_result())

    broken.edit.assert_not_called()
    pr.create_issue_comment.assert_called_once()


def test_upsert_sticky_skips_bot_comment_when_marker_not_at_start() -> None:
    bot = MagicMock()
    bot.body = f"See also {MARKER} below"
    bot.user.login = "github-actions[bot]"

    pr = MagicMock()
    pr.get_issue_comments.return_value = [bot]

    upsert_sticky(pr, _sample_result())

    bot.edit.assert_not_called()
    pr.create_issue_comment.assert_called_once()
