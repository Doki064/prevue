"""Tests for sticky PR comment upsert."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import responses

from prevue.classify.models import ClassificationResult
from prevue.dismiss import DismissEntry, parse_dismiss_block
from prevue.fingerprint import fingerprint
from prevue.gate import (
    GateResult,
    PlacedFinding,
    ReviewConfig,
    severity_counts_line,
    thresholds_line,
    verdict_title,
)
from prevue.github.comments import (
    BOT_LOGINS,
    INLINE_MARKER,
    LEGACY_INLINE_MARKER,
    MARKER,
    _escape_inline_markdown,
    _escape_table_cell,
    _is_prevue_inline_comment,
    _is_prevue_sticky,
    _safe_suggestion_block,
    derive_prior_findings,
    parse_marker_sha,
    parse_severity_from_body,
    post_inline_review,
    render_body,
    render_inline_comment,
    render_marker,
    resolve_outdated_prior_findings,
    upsert_skip_note,
    upsert_sticky,
)
from prevue.models import Finding, ReviewResult

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GRAPHQL_URL = "https://api.github.com/graphql"


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
    assert "<details><summary>Metadata</summary>" in body
    assert "fake" in body
    assert "0.1" in body


def test_render_body_dismiss_audit_section_round_trip() -> None:
    entry = DismissEntry(
        fingerprint="0123456789abcdef",
        path="src/example.py",
        region=(10, 20),
        side="RIGHT",
        severity="warning",
        actor="alice",
        timestamp="2026-06-16T00:00:00Z",
        reason="false positive",
    )
    body = render_body(_sample_result(), dismissals=[entry])

    assert "### Dismissed findings" in body
    assert "<!-- prevue:dismiss -->" in body
    assert entry.fingerprint in body
    assert parse_dismiss_block(body) == [entry]


def test_render_body_dismiss_none_no_regression() -> None:
    baseline = render_body(_sample_result())
    assert render_body(_sample_result(), dismissals=None) == baseline


def test_render_body_metadata_shows_labels_and_matched_globs() -> None:
    classification = ClassificationResult(
        labels={"frontend": "**/*.tsx"},
        bundles=["frontend"],
    )
    body = render_body(_sample_result(), classification=classification)

    assert "<details><summary>Metadata</summary>" in body
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


def test_render_body_label_value_backticks_escaped() -> None:
    """After LLM fallback, a label value can be an untrusted PR path; backticks in it
    must be escaped so they cannot break the inline code span / sticky layout."""
    classification = ClassificationResult(
        labels={"backend": "src/eval`rm -rf`.py"},
        bundles=["backend"],
    )
    body = render_body(_sample_result(), classification=classification)
    labels_section = body.split("Labels: ", 1)[1].split("\nBundles:", 1)[0]
    assert "\\`" in labels_section  # backtick escaped
    assert "`rm -rf`" not in labels_section  # raw unescaped span did not survive


def test_render_body_loaded_skills() -> None:
    body = render_body(
        _sample_result(),
        classification=ClassificationResult(
            labels={"security": "**/*"},
            bundles=["security"],
        ),
        loaded_skills=["Committed Secrets & Credentials (security)"],
    )

    assert "Skills: Committed Secrets & Credentials (security)" in body


def test_render_body_engine_from_meta() -> None:
    result = ReviewResult(
        summary_markdown="## Review",
        findings=[],
        engine_meta={"model": "fake", "duration_s": 0.1, "engine": "cursor-cli"},
    )
    body = render_body(result)

    assert "Engine: cursor-cli" in body
    assert "Engine: copilot-cli" not in body


def test_render_body_skill_consumer_source() -> None:
    body = render_body(
        _sample_result(),
        classification=ClassificationResult(
            labels={"security": "**/*"},
            bundles=["security"],
        ),
        loaded_skills=["Custom Rule (security, consumer)"],
    )

    assert "Skills: Custom Rule (security, consumer)" in body


def test_render_body_single_skills_line_with_loaded_and_ratios() -> None:
    """WR-01: loaded_skills + skill_ratios must not emit two conflicting Skills lines."""
    body = render_body(
        _sample_result(),
        classification=ClassificationResult(
            labels={"security": "**/*"},
            bundles=["security"],
        ),
        loaded_skills=["Committed Secrets & Credentials (security)"],
        skill_ratios={"security": (1, 2)},
    )

    assert body.count("\nSkills:") == 1
    assert "Skill coverage: 1/2 loaded" in body


def test_render_body_metadata_shows_dropped_count() -> None:
    """D-09: dropped-file count surfaced in Metadata audit trail."""
    classification = ClassificationResult(
        labels={"frontend": "**/*.tsx"},
        bundles=["frontend"],
        dropped_count=2,
    )
    body = render_body(_sample_result(), classification=classification)

    assert "2 filtered" in body


def test_upsert_skip_note_creates_sticky_with_dropped_count() -> None:
    pr = MagicMock()
    pr.get_issue_comments.return_value = []

    upsert_skip_note(pr, dropped_count=3)

    pr.create_issue_comment.assert_called_once()
    body = pr.create_issue_comment.call_args[0][0]
    assert body.startswith(MARKER)
    assert "no reviewable files" in body
    assert "3 filtered" in body


def test_upsert_skip_note_edits_existing_marker_comment() -> None:
    existing = MagicMock()
    existing.body = f"{MARKER}\nold skip note"
    existing.user.login = "github-actions[bot]"

    pr = MagicMock()
    pr.get_issue_comments.return_value = [existing]

    upsert_skip_note(pr, dropped_count=5)

    existing.edit.assert_called_once()
    pr.create_issue_comment.assert_not_called()
    body = existing.edit.call_args[0][0]
    assert "5 filtered" in body


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


def test_upsert_sticky_edits_existing_marker_comment_for_configured_owner(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PREVUE_STICKY_OWNER_LOGINS", "prevue-review[bot]")
    existing = MagicMock()
    existing.body = f"{MARKER}\nold content"
    existing.user.login = "prevue-review[bot]"

    pr = MagicMock()
    pr.get_issue_comments.return_value = [existing]

    upsert_sticky(pr, _sample_result())

    existing.edit.assert_called_once()
    pr.create_issue_comment.assert_not_called()


def test_upsert_sticky_does_not_edit_unrelated_bot_with_marker() -> None:
    unrelated_bot = MagicMock()
    unrelated_bot.body = f"{MARKER}\nthird-party bot sticky"
    unrelated_bot.user.login = "other-bot[bot]"

    pr = MagicMock()
    pr.get_issue_comments.return_value = [unrelated_bot]

    upsert_sticky(pr, _sample_result())

    unrelated_bot.edit.assert_not_called()
    pr.create_issue_comment.assert_called_once()


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


class TestPostInlineReview:
    def _finding(self, **overrides) -> Finding:
        defaults = {
            "path": "src/a.py",
            "line": 10,
            "severity": "error",
            "title": "Issue",
            "body": "Fix it.",
        }
        defaults.update(overrides)
        return Finding(**defaults)

    def _gate(self, inline: list[Finding]) -> GateResult:
        placed = [PlacedFinding(finding=f, placement="inline") for f in inline]
        return GateResult(
            conclusion="neutral",
            severity_counts={"error": len(inline), "warning": 0, "info": 0},
            placed=placed,
            inline=inline,
            config=ReviewConfig(),
        )

    def test_single_batched_comment_review(self) -> None:
        findings = [
            self._finding(path="a.py", line=1, title="A"),
            self._finding(path="b.py", line=2, title="B", severity="warning"),
        ]
        gate = self._gate(findings)
        pr = MagicMock()
        pr.get_review_comments.return_value = []

        assert post_inline_review(pr, gate) == set()

        pr.create_review.assert_called_once()
        kwargs = pr.create_review.call_args.kwargs
        assert kwargs["event"] == "COMMENT"
        assert kwargs["body"] == "Prevue posted 2 new inline comment(s) — see the review summary."
        assert len(kwargs["comments"]) == 2
        first = kwargs["comments"][0]
        assert set(first.keys()) == {"path", "line", "side", "body"}
        assert first["path"] == "a.py"
        assert first["line"] == 1
        assert first["body"] == render_inline_comment(findings[0])

    def test_skips_empty_inline(self) -> None:
        gate = GateResult(
            conclusion="success",
            severity_counts={"error": 0, "warning": 0, "info": 0},
            placed=[],
            inline=[],
            config=ReviewConfig(),
        )
        pr = MagicMock()
        pr.get_review_comments.return_value = []

        assert post_inline_review(pr, gate) == set()
        pr.create_review.assert_not_called()

    def test_swallows_github_exception(self, capsys) -> None:
        from github import GithubException

        gate = self._gate([self._finding(path="src/a.py", line=10)])
        pr = MagicMock()
        pr.get_review_comments.return_value = []
        pr.create_review.side_effect = GithubException(422, {"message": "Validation Failed"}, None)

        assert post_inline_review(pr, gate) == {("src/a.py", 10, "RIGHT")}
        err = capsys.readouterr().err
        assert "inline review POST failed" in err
        assert "1 comment" in err

    def test_updates_existing_inline_at_same_location(self) -> None:
        # Finding is severity "error"; prior body starts with warning badge "🟡" so
        # escalation is detected and the comment is updated (D-06 / WR-04).
        finding = self._finding(path="a.py", line=1, title="Updated")
        gate = self._gate([finding])
        existing = MagicMock()
        existing.path = "a.py"
        existing.line = 1
        existing.side = "RIGHT"
        existing.body = "🟡 **Old warning**\n\nFix it.\n\n<sub>posted by Prevue</sub>"
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]

        assert post_inline_review(pr, gate) == set()

        existing.edit.assert_called_once_with(render_inline_comment(finding))
        pr.create_review.assert_not_called()

    def test_posts_only_new_locations_when_some_exist(self) -> None:
        findings = [
            self._finding(path="a.py", line=1, title="A"),
            self._finding(path="b.py", line=2, title="B", severity="warning"),
        ]
        gate = self._gate(findings)
        existing = MagicMock()
        existing.path = "a.py"
        existing.line = 1
        existing.side = "RIGHT"
        # Prior a.py comment has "warning" badge; new finding is "error" → escalation
        # is detected and edit fires (D-06 / WR-04).
        existing.body = "🟡 **Old warning**\n\nFix it.\n\n<sub>posted by Prevue</sub>"
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]

        assert post_inline_review(pr, gate) == set()

        existing.edit.assert_called_once()
        pr.create_review.assert_called_once()
        kwargs = pr.create_review.call_args.kwargs
        assert len(kwargs["comments"]) == 1
        assert kwargs["comments"][0]["path"] == "b.py"
        assert "1 new inline comment(s)" in kwargs["body"]
        assert "1 updated in place" in kwargs["body"]

    def test_deletes_stale_inline_comments_on_rerun(self) -> None:
        gate = GateResult(
            conclusion="success",
            severity_counts={"error": 0, "warning": 0, "info": 0},
            placed=[],
            inline=[],
            config=ReviewConfig(),
        )
        stale = MagicMock()
        stale.path = "old.py"
        stale.line = 9
        stale.side = "RIGHT"
        stale.body = "stale\n\n<sub>posted by Prevue</sub>"
        stale.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [stale]

        assert post_inline_review(pr, gate) == set()

        pr.create_review.assert_not_called()
        stale.delete.assert_called_once()

    def test_deletes_outdated_line_null_inline_in_scope(self) -> None:
        """Outdated GitHub threads (line=None) are removed on in-scope re-run."""
        gate = GateResult(
            conclusion="success",
            severity_counts={"error": 0, "warning": 0, "info": 0},
            placed=[],
            inline=[],
            config=ReviewConfig(),
        )
        outdated = MagicMock()
        outdated.path = "src/test2.js"
        outdated.line = None
        outdated.original_line = 1
        outdated.side = "RIGHT"
        outdated.body = (
            "🔴 **Undefined identifier console2**\n\n<body>\n\n<sub>posted by Prevue</sub>"
        )
        outdated.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [outdated]

        assert post_inline_review(pr, gate, in_scope_paths={"src/test2.js"}) == set()

        outdated.delete.assert_called_once()
        pr.create_review.assert_not_called()

    def test_outdated_line_null_out_of_scope_not_deleted(self) -> None:
        gate = GateResult(
            conclusion="success",
            severity_counts={"error": 0, "warning": 0, "info": 0},
            placed=[],
            inline=[],
            config=ReviewConfig(),
        )
        outdated = MagicMock()
        outdated.path = "other.py"
        outdated.line = None
        outdated.side = "RIGHT"
        outdated.body = "🔴 **Issue**\n\n<body>\n\n<sub>posted by Prevue</sub>"
        outdated.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [outdated]

        post_inline_review(pr, gate, in_scope_paths={"a.py"})

        outdated.delete.assert_not_called()

    def test_create_failure_still_deletes_stale(self) -> None:
        """Create failure is non-fatal for cleanup: stale comments must still be
        removed so the PR does not end with old + new threads coexisting."""
        from github import GithubException

        gate = self._gate([self._finding(path="new.py", line=5)])
        stale = MagicMock()
        stale.path = "old.py"
        stale.line = 9
        stale.side = "RIGHT"
        stale.body = "stale\n\n<sub>posted by Prevue</sub>"
        stale.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [stale]
        pr.create_review.side_effect = GithubException(422, {"message": "Validation Failed"}, None)

        assert post_inline_review(pr, gate) == {("new.py", 5, "RIGHT")}

        stale.delete.assert_called_once()

    def test_edits_run_before_create_even_if_create_fails(self) -> None:
        """Existing comments are edited before creating new ones, so a create
        failure cannot leave the existing thread showing stale content. Only the
        failed create is reported as failed; the successful edit is not downgraded."""
        from github import GithubException

        findings = [
            self._finding(path="existing.py", line=1, title="Existing"),
            self._finding(path="new.py", line=5, title="New"),
        ]
        gate = self._gate(findings)
        existing = MagicMock()
        existing.path = "existing.py"
        existing.line = 1
        existing.side = "RIGHT"
        existing.body = "🟡 **Old warning**\n\nFix it.\n\n<sub>posted by Prevue</sub>"
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]
        pr.create_review.side_effect = GithubException(422, {"message": "Validation Failed"}, None)

        assert post_inline_review(pr, gate) == {("new.py", 5, "RIGHT")}

        pr.create_review.assert_called_once()
        existing.edit.assert_called_once()

    def test_edit_failure_is_nonfatal_and_still_deletes_stale(self) -> None:
        """An edit failure flags only that location as failed and does not abort
        the function before stale cleanup runs."""
        from github import GithubException

        gate = self._gate([self._finding(path="existing.py", line=1, title="Existing")])
        existing = MagicMock()
        existing.path = "existing.py"
        existing.line = 1
        existing.side = "RIGHT"
        existing.body = "🟡 **Old warning**\n\nFix it.\n\n<sub>posted by Prevue</sub>"
        existing.user.login = "github-actions[bot]"
        existing.edit.side_effect = GithubException(422, {"message": "Validation Failed"}, None)
        stale = MagicMock()
        stale.path = "old.py"
        stale.line = 9
        stale.side = "RIGHT"
        stale.body = "stale\n\n<sub>posted by Prevue</sub>"
        stale.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing, stale]

        assert post_inline_review(pr, gate) == {("existing.py", 1, "RIGHT")}

        existing.edit.assert_called_once()
        stale.delete.assert_called_once()
        pr.create_review.assert_not_called()

    def test_partial_success_reports_only_failed_keys(self) -> None:
        """Edit succeeds + create fails → only the created (failed) location is
        returned, so review.py keeps the edited finding inline (no misreport)."""
        from github import GithubException

        findings = [
            self._finding(path="edited.py", line=1, title="Edited"),
            self._finding(path="created.py", line=5, title="Created"),
        ]
        gate = self._gate(findings)
        existing = MagicMock()
        existing.path = "edited.py"
        existing.line = 1
        existing.side = "RIGHT"
        existing.body = "🟡 **Old warning**\n\nFix it.\n\n<sub>posted by Prevue</sub>"
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]
        pr.create_review.side_effect = GithubException(422, {"message": "Validation Failed"}, None)

        failed = post_inline_review(pr, gate)

        assert failed == {("created.py", 5, "RIGHT")}
        assert ("edited.py", 1, "RIGHT") not in failed
        existing.edit.assert_called_once()

    def test_stale_delete_failure_does_not_block_post(self) -> None:
        from github import GithubException

        gate = self._gate([self._finding(path="a.py", line=1)])
        stale = MagicMock()
        stale.path = "old.py"
        stale.line = 9
        stale.side = "RIGHT"
        stale.body = "stale\n\n<sub>posted by Prevue</sub>"
        stale.user.login = "github-actions[bot]"
        stale.delete.side_effect = GithubException(403, {"message": "Forbidden"}, None)
        pr = MagicMock()
        pr.get_review_comments.return_value = [stale]

        assert post_inline_review(pr, gate) == set()

        pr.create_review.assert_called_once()
        stale.delete.assert_called_once()

    def test_scoped_carry_forward_preserves_out_of_scope_comment(self) -> None:
        """Push 2 reviews only file A; file B prior comment untouched (D-05)."""
        finding = self._finding(path="a.py", line=1, title="A issue")
        gate = self._gate([finding])
        out_of_scope = MagicMock()
        out_of_scope.path = "b.py"
        out_of_scope.line = 5
        out_of_scope.side = "RIGHT"
        out_of_scope.body = "🟡 **B issue**\n\nOld body.\n\n<sub>posted by Prevue</sub>"
        out_of_scope.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [out_of_scope]

        assert post_inline_review(pr, gate, in_scope_paths={"a.py"}) == set()

        out_of_scope.edit.assert_not_called()
        out_of_scope.delete.assert_not_called()
        pr.create_review.assert_called_once()

    def test_escalation_equal_severity_skips_edit(self) -> None:
        """Same severity at same location → no churn (D-06)."""
        finding = self._finding(path="a.py", line=1, severity="warning", title="Lint")
        gate = self._gate([finding])
        existing = MagicMock()
        existing.path = "a.py"
        existing.line = 1
        existing.side = "RIGHT"
        existing.body = render_inline_comment(self._finding(severity="warning", title="Lint"))
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]

        assert post_inline_review(pr, gate) == set()

        existing.edit.assert_not_called()
        pr.create_review.assert_not_called()

    def test_escalation_warning_to_error_calls_edit(self) -> None:
        """Severity escalation refreshes comment in place (D-06)."""
        finding = self._finding(path="a.py", line=1, severity="error", title="Lint")
        gate = self._gate([finding])
        existing = MagicMock()
        existing.path = "a.py"
        existing.line = 1
        existing.side = "RIGHT"
        existing.body = render_inline_comment(self._finding(severity="warning", title="Lint"))
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]

        assert post_inline_review(pr, gate) == set()

        existing.edit.assert_called_once_with(render_inline_comment(finding))
        pr.create_review.assert_not_called()

    def test_deescalation_error_to_warning_calls_edit(self) -> None:
        """Severity de-escalation refreshes badge so stale emoji does not linger."""
        finding = self._finding(path="a.py", line=1, severity="warning", title="Lint")
        gate = self._gate([finding])
        existing = MagicMock()
        existing.path = "a.py"
        existing.line = 1
        existing.side = "RIGHT"
        existing.body = render_inline_comment(self._finding(severity="error", title="Lint"))
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]

        assert post_inline_review(pr, gate) == set()

        existing.edit.assert_called_once_with(render_inline_comment(finding))
        pr.create_review.assert_not_called()

    def test_scoped_duplicate_at_key_still_deleted(self) -> None:
        """Own same-run duplicate extras are hard-deleted (existing path)."""
        finding = self._finding(path="a.py", line=1, title="A", severity="warning")
        gate = self._gate([finding])
        primary = MagicMock()
        primary.path = "a.py"
        primary.line = 1
        primary.side = "RIGHT"
        primary.body = render_inline_comment(self._finding(severity="warning", title="A"))
        primary.user.login = "github-actions[bot]"
        duplicate = MagicMock()
        duplicate.path = "a.py"
        duplicate.line = 1
        duplicate.side = "RIGHT"
        duplicate.body = "🟡 **A**\n\nDup.\n\n<sub>posted by Prevue</sub>"
        duplicate.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [primary, duplicate]

        assert post_inline_review(pr, gate, in_scope_paths={"a.py"}) == set()

        duplicate.delete.assert_called_once()
        primary.edit.assert_not_called()

    def test_rephrase_at_same_line_keeps_inline_unchanged(self) -> None:
        """Rephrase-at-same-line: current finding has a DIFFERENT fingerprint at the
        same (path, line, side) as an existing inline, but equal severity.
        D-06 (fingerprint-aligned skip): must NOT call .edit() and must NOT create
        a duplicate inline at that location."""
        prior_finding = self._finding(
            path="src/test1.js",
            line=4,
            severity="error",
            title="Invalid Console.log — use console.log",
        )
        # Current engine finding at same location with DIFFERENT title (new fingerprint).
        current_finding = self._finding(
            path="src/test1.js",
            line=4,
            severity="error",
            title="Console.log uses wrong identifier casing",
        )
        gate = self._gate([current_finding])

        # Existing inline comment body built from render_inline_comment so the
        # _parse_title_from_inline_body round-trip works correctly.
        existing = MagicMock()
        existing.path = "src/test1.js"
        existing.line = 4
        existing.side = "RIGHT"
        existing.body = render_inline_comment(prior_finding)
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]

        assert post_inline_review(pr, gate) == set()

        # No edit because fingerprints differ but severity did not escalate.
        existing.edit.assert_not_called()
        # No duplicate inline created at this location.
        if pr.create_review.called:
            kwargs = pr.create_review.call_args.kwargs
            created_paths_lines = [(c["path"], c["line"]) for c in kwargs.get("comments", [])]
            assert ("src/test1.js", 4) not in created_paths_lines, (
                "Must not create a duplicate inline at the rephrase location"
            )


class TestStickyWithGate:
    def _finding(self, **overrides) -> Finding:
        defaults = {
            "path": "src/a.py",
            "line": 10,
            "severity": "error",
            "title": "Issue",
            "body": "Details here.",
        }
        defaults.update(overrides)
        return Finding(**defaults)

    def _gate(self, **overrides) -> GateResult:
        findings = [
            self._finding(path="a.py", line=1, severity="error", title="E1"),
            self._finding(path="b.py", line=2, severity="warning", title="W1"),
            self._finding(path="c.py", line=3, severity="info", title="I1"),
            self._finding(path="d.py", line=4, severity="warning", title="W2"),
        ]
        placed = [
            PlacedFinding(finding=findings[0], placement="inline"),
            PlacedFinding(finding=findings[1], placement="inline"),
            PlacedFinding(finding=findings[2], placement="summary-only"),
            PlacedFinding(finding=findings[3], placement="position-fallback"),
        ]
        defaults: dict = {
            "conclusion": "neutral",
            "severity_counts": {"error": 1, "warning": 2, "info": 1},
            "placed": placed,
            "inline": [findings[0], findings[1]],
            "config": ReviewConfig(),
            "degraded": False,
            "dropped_findings": 0,
        }
        defaults.update(overrides)
        return GateResult(**defaults)

    def test_section_order_with_gate(self) -> None:
        body = render_body(_sample_result(), gate=self._gate())
        verdict_idx = body.index("### Verdict")
        review_idx = body.index("### Review")
        findings_idx = body.index("### Findings")
        metadata_idx = body.index("<details><summary>Metadata</summary>")
        assert verdict_idx < review_idx < findings_idx < metadata_idx
        assert body.index("<details>") > findings_idx

    def test_verdict_mirrors_gate_helpers(self) -> None:
        gate = self._gate()
        body = render_body(_sample_result(), gate=gate)

        assert verdict_title(gate) in body
        assert severity_counts_line(gate) in body
        assert thresholds_line(gate) in body
        # WR-02: thresholds belong under Verdict only — not duplicated in Metadata.
        assert body.count("Thresholds:") == 1

    def test_findings_table_row_count(self) -> None:
        body = render_body(_sample_result(), gate=self._gate())

        table_lines = [
            line
            for line in body.split("\n")
            if line.startswith("|") and "Severity" not in line and "---" not in line
        ]
        assert len(table_lines) == 4

    def test_details_only_for_non_inline(self) -> None:
        body = render_body(_sample_result(), gate=self._gate())

        assert body.count("<details>") == 3  # 2 non-inline findings + collapsible metadata
        assert "c.py:3 — I1" in body
        assert "d.py:4 — W2" in body

    def test_degraded_notice_in_metadata(self) -> None:
        gate = self._gate(degraded=True, placed=[], inline=[])
        body = render_body(_sample_result(), gate=gate)

        assert "structured findings unavailable (parse failure)" in body

    def test_gate_none_preserves_phase3_output(self) -> None:
        without_gate = render_body(_sample_result())
        assert "_No verdict in v1 — informational review only._" in without_gate
        assert "### Findings" not in without_gate

    def test_table_escapes_pipe_in_title(self) -> None:
        finding = self._finding(title="bad|pipe", path="x.py", line=5)
        gate = GateResult(
            conclusion="neutral",
            severity_counts={"error": 1, "warning": 0, "info": 0},
            placed=[PlacedFinding(finding=finding, placement="inline")],
            inline=[finding],
            config=ReviewConfig(),
        )
        body = render_body(_sample_result(), gate=gate)

        assert "bad\\|pipe" in body
        assert "| 🔴 error | `x.py:5` | bad\\|pipe | 💬 inline |" in body

    def test_table_neutralizes_html_in_title(self) -> None:
        finding = self._finding(title="<b>x</b>", path="x.py", line=5)
        gate = GateResult(
            conclusion="neutral",
            severity_counts={"error": 1, "warning": 0, "info": 0},
            placed=[PlacedFinding(finding=finding, placement="inline")],
            inline=[finding],
            config=ReviewConfig(),
        )
        body = render_body(_sample_result(), gate=gate)
        assert "<b>" not in body
        assert "&lt;b>x&lt;/b>" in body

    def test_upsert_sticky_returns_created_comment(self) -> None:
        created = MagicMock()
        pr = MagicMock()
        pr.get_issue_comments.return_value = []
        pr.create_issue_comment.return_value = created

        assert upsert_sticky(pr, _sample_result()) is created

    def test_upsert_sticky_returns_edited_comment(self) -> None:
        existing = MagicMock()
        existing.body = f"{MARKER}\nold content"
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_issue_comments.return_value = [existing]

        assert upsert_sticky(pr, _sample_result()) is existing

    def test_upsert_skip_note_returns_comment(self) -> None:
        created = MagicMock()
        pr = MagicMock()
        pr.get_issue_comments.return_value = []
        pr.create_issue_comment.return_value = created

        assert upsert_skip_note(pr, dropped_count=2) is created

    def test_skipped_files_disclosure(self) -> None:
        body = render_body(
            _sample_result(),
            gate=self._gate(),
            skipped_paths=["docs/readme.md", "assets/logo.png"],
            skipped_reason="security/risk-weighted whole-file packing",
        )

        assert "2 files not reviewed (over token budget)" in body
        assert "<details>" in body
        assert "`docs/readme.md`" in body
        assert "`assets/logo.png`" in body
        assert body.index("### Coverage") < body.index("<details><summary>Metadata</summary>")

    def test_skipped_reason_html_escaped_in_summary(self) -> None:
        """A skipped_reason containing HTML cannot break out of the <summary> wrapper."""
        body = render_body(
            _sample_result(),
            gate=self._gate(),
            skipped_paths=["docs/readme.md"],
            skipped_reason="boom</summary><script>alert(1)</script>",
        )
        # Escaping the leading `<` (as render_finding_details does) is enough to stop
        # the tag closing the wrapper — the raw `</summary><script>` must not survive.
        assert "boom</summary>" not in body
        assert "<script>" not in body
        assert "boom&lt;/summary>&lt;script>" in body

    def test_llm_summary_html_comment_neutralized(self) -> None:
        """An HTML comment / declaration in untrusted LLM summary is neutralized too
        (not only tags), so it cannot hide content or aid a <details> breakout."""
        result = ReviewResult(
            summary_markdown="ok <!-- </details> --> <?php ?> done",
            findings=[],
            engine_meta={"model": "fake", "duration_s": 0.1},
        )
        body = render_body(result, gate=self._gate())
        # Scope to the Review section — the sticky MARKER is itself an HTML comment.
        review = body.split("### Review\n", 1)[1].split("\n\n", 1)[0]
        assert "<!--" not in review
        assert "<?php" not in review
        assert "&lt;!--" in review
        assert "&lt;?php" in review

    def test_token_line_estimated(self) -> None:
        body = render_body(
            _sample_result(),
            token_meta={"review": 1200, "classify": 80, "estimated": True},
        )
        assert "Tokens: review ~est 1200" in body
        assert "classify ~est 80" in body

    def test_token_line_per_metric_provenance(self) -> None:
        """WR-03: review can be exact while classify is estimated — markers independent."""
        body = render_body(
            _sample_result(),
            token_meta={
                "review": 1200,
                "classify": 80,
                "review_estimated": False,
                "classify_estimated": True,
            },
        )
        assert "Tokens: review 1200" in body
        assert "review ~est" not in body
        assert "classify ~est 80" in body

    def test_per_bundle_ratio_line(self) -> None:
        body = render_body(
            _sample_result(),
            skill_ratios={
                "security": (2, 3),
                "frontend": (1, 4),
                "backend": (0, 3),
            },
        )
        assert "Skill coverage: 3/10 loaded" in body
        assert "security 2/3" in body
        assert "frontend 1/4" in body
        assert "backend 0/3" in body


class TestInlineTemplate:
    def _finding(self, **overrides) -> Finding:
        defaults = {
            "path": "src/a.py",
            "line": 10,
            "severity": "error",
            "title": "SQL injection",
            "body": "Use parameterized queries.",
            "suggestion": None,
        }
        defaults.update(overrides)
        return Finding(**defaults)

    def test_error_badge_title_body_footer_no_suggestion(self) -> None:
        rendered = render_inline_comment(self._finding())

        lines = rendered.split("\n")
        assert lines[0] == "🔴 **SQL injection**"
        assert lines[1] == ""
        assert lines[2] == "Use parameterized queries."
        assert "**Suggested change**" not in rendered
        assert rendered.endswith("_posted by Prevue_")

    def test_warning_and_info_badges(self) -> None:
        warning = render_inline_comment(self._finding(severity="warning", title="Lint"))
        info = render_inline_comment(self._finding(severity="info", title="Note"))

        assert warning.startswith("🟡 **Lint**")
        assert info.startswith("🔵 **Note**")

    def test_suggestion_in_four_backtick_fence(self) -> None:
        rendered = render_inline_comment(self._finding(suggestion="cursor.execute(query, params)"))

        assert "**Suggested change**" in rendered
        assert "````\ncursor.execute(query, params)\n````" in rendered

    def test_suggestion_escapes_triple_backticks(self) -> None:
        rendered = render_inline_comment(self._finding(suggestion="code with ``` inside"))

        assert "````\ncode with ``` inside\n````" in rendered

    def test_suggestion_with_four_backticks_uses_longer_fence(self) -> None:
        rendered = render_inline_comment(self._finding(suggestion="code with ```` inside"))

        assert "`````\ncode with ```` inside\n`````" in rendered

    def test_uniform_template_structure(self) -> None:
        a = render_inline_comment(self._finding(title="A", body="body A"))
        b = render_inline_comment(self._finding(severity="warning", title="B", body="body B"))

        def skeleton(text: str) -> list[str]:
            lines = text.split("\n")
            return [
                "BADGE_TITLE" if line.startswith(("🔴", "🟡", "🔵")) else line
                for line in lines
                if line not in {"body A", "body B"}
            ]

        assert skeleton(a) == skeleton(b)

    def test_escape_table_cell_pipes_and_newlines(self) -> None:
        assert _escape_table_cell("a|b\nc") == "a\\|b c"
        assert _escape_table_cell("a\r\nb") == "a b"

    def test_inline_title_escapes_markdown_control_chars(self) -> None:
        rendered = render_inline_comment(self._finding(title="bad_*[title]`value`", body="details"))
        assert "🔴 **bad\\_\\*\\[title\\]\\`value\\`**" in rendered

    def test_inline_body_escapes_markdown_control_chars(self) -> None:
        rendered = render_inline_comment(self._finding(body="ping [link](x) and `code`"))
        assert "ping \\[link\\](x) and \\`code\\`" in rendered

    def test_inline_comment_neutralizes_html(self) -> None:
        """Inline comments render to all PR viewers — HTML in title/body must be encoded."""
        rendered = render_inline_comment(
            self._finding(title="<img src=x onerror=alert(1)>", body="<script>evil()</script>")
        )
        assert "<img" not in rendered
        assert "<script>" not in rendered
        assert "&lt;img" in rendered
        assert "&lt;script>" in rendered

    def test_parse_title_handles_legacy_badge_without_bold(self) -> None:
        """Legacy inline comments with a badge but no **bold** title still carry forward."""
        from prevue.github.comments import _parse_title_from_inline_body

        assert (
            _parse_title_from_inline_body("🔴 Legacy plain title\n\nbody here")
            == "Legacy plain title"
        )
        # Bold form still takes precedence and is unwrapped.
        assert _parse_title_from_inline_body("🟡 **Bold title**\n\nbody") == "Bold title"


class TestInlineMarkerDetection:
    """Marker detection tests: new GFM marker and legacy <sub> backward compat."""

    def _trusted_comment(self, body: str) -> MagicMock:
        comment = MagicMock()
        comment.body = body
        comment.user.login = "github-actions[bot]"
        return comment

    def test_new_gfm_marker_is_detected(self) -> None:
        """New _posted by Prevue_ GFM marker is detected by _is_prevue_inline_comment."""
        body = f"🔴 **Issue**\n\nDetails.\n\n{INLINE_MARKER}"
        comment = self._trusted_comment(body)
        assert _is_prevue_inline_comment(comment) is True

    def test_legacy_sub_marker_still_detected(self) -> None:
        """Legacy <sub>posted by Prevue</sub> (pre-migration, e.g. PR #23) still detected."""
        body = f"🔴 **Old issue**\n\nDetails.\n\n{LEGACY_INLINE_MARKER}"
        comment = self._trusted_comment(body)
        assert _is_prevue_inline_comment(comment) is True

    def test_no_marker_not_detected(self) -> None:
        """Body without any Prevue marker is not detected."""
        body = "🔴 **Issue**\n\nNo marker here."
        comment = self._trusted_comment(body)
        assert _is_prevue_inline_comment(comment) is False

    def test_inline_marker_constant_is_gfm_safe(self) -> None:
        """INLINE_MARKER must not contain HTML tags."""
        assert "<" not in INLINE_MARKER
        assert ">" not in INLINE_MARKER
        assert INLINE_MARKER == "_posted by Prevue_"

    def test_legacy_inline_marker_constant_is_preserved(self) -> None:
        """LEGACY_INLINE_MARKER retains the old HTML form for backward-compat detection."""
        assert LEGACY_INLINE_MARKER == "<sub>posted by Prevue</sub>"

    def test_render_inline_comment_uses_new_gfm_marker(self) -> None:
        """render_inline_comment appends the new GFM marker, not the legacy HTML."""
        from prevue.models import Finding

        finding = Finding(path="a.py", line=1, severity="error", title="T", body="B")
        rendered = render_inline_comment(finding)
        assert rendered.endswith(INLINE_MARKER)
        assert LEGACY_INLINE_MARKER not in rendered


def test_upsert_sticky_skips_bot_comment_when_marker_not_at_start() -> None:
    bot = MagicMock()
    bot.body = f"See also {MARKER} below"
    bot.user.login = "github-actions[bot]"

    pr = MagicMock()
    pr.get_issue_comments.return_value = [bot]

    upsert_sticky(pr, _sample_result())

    bot.edit.assert_not_called()
    pr.create_issue_comment.assert_called_once()


def test_safe_suggestion_uses_fence_longer_than_backtick_run() -> None:
    block = _safe_suggestion_block("alpha ``` beta ```` gamma")
    assert block.startswith("`````")
    assert block.endswith("`````")


def test_escape_inline_markdown_collapses_newlines() -> None:
    assert _escape_inline_markdown("row1\nrow2") == "row1 row2"


class TestSeverityParseBack:
    def _finding(self, **overrides) -> Finding:
        defaults = {
            "path": "src/a.py",
            "line": 10,
            "severity": "error",
            "title": "Issue",
            "body": "Fix it.",
        }
        defaults.update(overrides)
        return Finding(**defaults)

    def test_severity_round_trip_all_levels(self) -> None:
        for severity in ("error", "warning", "info"):
            finding = self._finding(severity=severity, title=f"{severity} title")
            rendered = render_inline_comment(finding)
            assert parse_severity_from_body(rendered) == severity

    def test_leading_badge_anchoring(self) -> None:
        assert parse_severity_from_body("🔴 **Something**") == "error"
        assert parse_severity_from_body("🟡 **Lint**") == "warning"
        assert parse_severity_from_body("🔵 **Note**") == "info"

    def test_human_comment_without_badge_returns_none(self) -> None:
        assert parse_severity_from_body("Looks good to me, ship it.") is None

    def test_legacy_alternate_template_with_leading_badge(self) -> None:
        legacy = "🔴 Old template title\n\nDetails without bold wrapper."
        assert parse_severity_from_body(legacy) == "error"

    def test_empty_body_returns_none(self) -> None:
        assert parse_severity_from_body("") is None

    def test_whitespace_only_body_returns_none(self) -> None:
        assert parse_severity_from_body("   \n  \n") is None


class TestMarkerSha:
    HEAD_SHA = "abc123def456789012345678901234567890abcd"

    def test_render_marker_sha_round_trip(self) -> None:
        marker = render_marker(self.HEAD_SHA)
        assert marker == f"<!-- prevue:sticky head={self.HEAD_SHA} -->"
        assert parse_marker_sha(marker) == self.HEAD_SHA

    def test_parse_legacy_headless_marker_returns_none(self) -> None:
        assert parse_marker_sha("<!-- prevue:sticky -->") is None
        assert parse_marker_sha(f"{MARKER}\n## Prevue Review\n\nold body") is None

    def test_parse_no_marker_returns_none(self) -> None:
        assert parse_marker_sha("## Prevue Review\n\nno marker here") is None
        assert parse_marker_sha("") is None

    def test_non_hex_sha_rejected(self) -> None:
        injected = "<!-- prevue:sticky head=../../etc/passwd -->"
        assert parse_marker_sha(injected) is None
        assert parse_marker_sha("<!-- prevue:sticky head=not-a-sha -->") is None

    def test_is_prevue_sticky_detects_legacy_marker(self) -> None:
        comment = MagicMock()
        comment.body = f"{MARKER}\n## Prevue Review"
        comment.user.login = next(iter(BOT_LOGINS))
        assert _is_prevue_sticky(comment) is True

    def test_is_prevue_sticky_detects_head_bearing_marker(self) -> None:
        comment = MagicMock()
        comment.body = f"{render_marker(self.HEAD_SHA)}\n## Prevue Review"
        comment.user.login = next(iter(BOT_LOGINS))
        assert _is_prevue_sticky(comment) is True


def _load_fixture(name: str) -> dict:
    with (FIXTURES_DIR / name).open() as f:
        return json.load(f)


def _register_graphql(rsps: responses.RequestsMock, payload: dict, *, status: int = 200) -> None:
    rsps.add(
        responses.POST,
        re.compile(rf"{re.escape(GRAPHQL_URL)}/?$"),
        json=payload,
        status=status,
    )


@pytest.fixture
def github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")


class TestPriorFindings:
    def _prevue_inline(self, path: str, line: int, finding: Finding) -> MagicMock:
        comment = MagicMock()
        comment.path = path
        comment.line = line
        comment.side = "RIGHT"
        comment.body = render_inline_comment(finding)
        comment.user.login = "github-actions[bot]"
        return comment

    @responses.activate
    def test_derive_prior_findings_from_live_comments(self, github_env: None) -> None:
        finding = Finding(
            path="src/prevue/review.py",
            line=142,
            severity="warning",
            title="Missing error handling",
            body="Handle engine failures explicitly.",
        )
        pr = MagicMock()
        pr.number = 42
        pr.get_review_comments.return_value = [
            self._prevue_inline("src/prevue/review.py", 142, finding)
        ]
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))

        priors = derive_prior_findings(pr, owner="owner", repo="prevue")

        assert len(priors) == 1
        prior = priors[0]
        assert prior.path == "src/prevue/review.py"
        assert prior.line == 142
        assert prior.severity == "warning"
        assert prior.fingerprint == fingerprint("src/prevue/review.py", "Missing error handling")
        assert prior.thread_id == "RT_kwDOExampleOpen0001"

    @responses.activate
    def test_derive_prior_findings_skips_resolved_thread(self, github_env: None) -> None:
        """A resolved thread is a closed finding (D-11) — must not be carried as a prior."""
        finding = Finding(
            path="src/prevue/github/diff.py",
            line=18,
            severity="error",
            title="SQL injection risk",
            body="Use parameterized queries.",
        )
        pr = MagicMock()
        pr.number = 42
        pr.get_review_comments.return_value = [
            self._prevue_inline("src/prevue/github/diff.py", 18, finding)
        ]
        # Fixture marks the diff.py:18 thread (RT_kwDOExampleResolved01) isResolved=true.
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))

        priors = derive_prior_findings(pr, owner="owner", repo="prevue")

        assert priors == []

    def test_derive_prior_findings_skips_outdated_line_null(self, github_env: None) -> None:
        """GitHub REST returns line=None on outdated threads — must not crash Finding validation."""
        finding = Finding(
            path="src/test2.js",
            line=1,
            severity="error",
            title="Undefined identifier console2",
            body="console2 is not defined.",
        )
        outdated = self._prevue_inline("src/test2.js", 1, finding)
        outdated.line = None
        outdated.original_line = 1

        pr = MagicMock()
        pr.number = 42
        pr.get_review_comments.return_value = [outdated]

        priors = derive_prior_findings(pr)

        assert priors == []


class TestOutdatedResolve:
    OWNER = "owner"
    REPO = "prevue"
    PATH = "src/prevue/review.py"
    LINE = 142
    TITLE = "Missing error handling"

    def _prior_comment(self) -> MagicMock:
        finding = Finding(
            path=self.PATH,
            line=self.LINE,
            severity="warning",
            title=self.TITLE,
            body="Handle engine failures explicitly.",
        )
        comment = MagicMock()
        comment.path = self.PATH
        comment.line = self.LINE
        comment.side = "RIGHT"
        comment.body = render_inline_comment(finding)
        comment.user.login = "github-actions[bot]"
        return comment

    def _pr(self) -> MagicMock:
        pr = MagicMock()
        pr.number = 42
        pr.get_review_comments.return_value = [self._prior_comment()]
        return pr

    @responses.activate
    def test_outdated_resolve_when_all_three_conditions_hold(self, github_env: None) -> None:
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))
        _register_graphql(responses.mock, _load_fixture("graphql_resolve_ok.json"))

        resolve_outdated_prior_findings(
            self._pr(),
            in_scope_paths={self.PATH},
            regions_by_path={self.PATH: [(140, 145)]},
            current_fingerprints=set(),
            owner=self.OWNER,
            repo=self.REPO,
        )

        assert len(responses.mock.calls) == 2

    @responses.activate
    def test_outdated_skips_out_of_scope_prior(self, github_env: None) -> None:
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))

        resolve_outdated_prior_findings(
            self._pr(),
            in_scope_paths={"other.py"},
            regions_by_path={self.PATH: [(140, 145)]},
            current_fingerprints=set(),
            owner=self.OWNER,
            repo=self.REPO,
        )

        assert len(responses.mock.calls) == 1

    @responses.activate
    def test_outdated_skips_unchanged_region(self, github_env: None) -> None:
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))

        resolve_outdated_prior_findings(
            self._pr(),
            in_scope_paths={self.PATH},
            regions_by_path={self.PATH: [(100, 110)]},
            current_fingerprints=set(),
            owner=self.OWNER,
            repo=self.REPO,
        )

        assert len(responses.mock.calls) == 1

    @responses.activate
    def test_authoritative_resolve_when_region_unchanged(self, github_env: None) -> None:
        """D-13: full-run authoritative resolve skips the region gate."""
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))
        _register_graphql(responses.mock, _load_fixture("graphql_resolve_ok.json"))

        resolve_outdated_prior_findings(
            self._pr(),
            in_scope_paths={self.PATH},
            regions_by_path={self.PATH: [(100, 110)]},
            current_fingerprints=set(),
            owner=self.OWNER,
            repo=self.REPO,
            authoritative=True,
        )

        assert len(responses.mock.calls) == 2

    @responses.activate
    def test_authoritative_resolve_keeps_present_fingerprint(self, github_env: None) -> None:
        """D-13: engine still emits same fingerprint — never resolve."""
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))

        prior_fp = fingerprint(self.PATH, self.TITLE)
        resolve_outdated_prior_findings(
            self._pr(),
            in_scope_paths={self.PATH},
            regions_by_path={self.PATH: [(100, 110)]},
            current_fingerprints={prior_fp},
            owner=self.OWNER,
            repo=self.REPO,
            authoritative=True,
        )

        assert len(responses.mock.calls) == 1

    @responses.activate
    def test_authoritative_skips_out_of_scope_prior(self, github_env: None) -> None:
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))

        resolve_outdated_prior_findings(
            self._pr(),
            in_scope_paths={"other.py"},
            regions_by_path={self.PATH: [(140, 145)]},
            current_fingerprints=set(),
            owner=self.OWNER,
            repo=self.REPO,
            authoritative=True,
        )

        assert len(responses.mock.calls) == 1

    @responses.activate
    def test_outdated_skips_when_fingerprint_in_current(self, github_env: None) -> None:
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))

        prior_fp = fingerprint(self.PATH, self.TITLE)
        resolve_outdated_prior_findings(
            self._pr(),
            in_scope_paths={self.PATH},
            regions_by_path={self.PATH: [(140, 145)]},
            current_fingerprints={prior_fp},
            owner=self.OWNER,
            repo=self.REPO,
        )

        assert len(responses.mock.calls) == 1

    @responses.activate
    def test_outdated_skips_already_resolved_thread(self, github_env: None) -> None:
        resolved_path = "src/prevue/github/diff.py"
        resolved_line = 18
        finding = Finding(
            path=resolved_path,
            line=resolved_line,
            severity="error",
            title="SQL injection risk",
            body="Use parameterized queries.",
        )
        comment = MagicMock()
        comment.path = resolved_path
        comment.line = resolved_line
        comment.side = "RIGHT"
        comment.body = render_inline_comment(finding)
        comment.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.number = 42
        pr.get_review_comments.return_value = [comment]
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))

        resolve_outdated_prior_findings(
            pr,
            in_scope_paths={resolved_path},
            regions_by_path={resolved_path: [(15, 20)]},
            current_fingerprints=set(),
            owner=self.OWNER,
            repo=self.REPO,
        )

        assert len(responses.mock.calls) == 1

    @responses.activate
    def test_outdated_403_logged_run_continues(self, github_env: None, capsys) -> None:
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))
        _register_graphql(responses.mock, _load_fixture("graphql_forbidden.json"))

        resolve_outdated_prior_findings(
            self._pr(),
            in_scope_paths={self.PATH},
            regions_by_path={self.PATH: [(140, 145)]},
            current_fingerprints=set(),
            owner=self.OWNER,
            repo=self.REPO,
        )

        err = capsys.readouterr().err
        assert "prevue: review thread resolve failed" in err
        assert "FORBIDDEN" in err
        assert len(responses.mock.calls) == 2

    @responses.activate
    def test_post_inline_resolve_outdated_integration(self, github_env: None) -> None:
        """post_inline_review with resolve_outdated triggers conservative resolve."""
        _register_graphql(responses.mock, _load_fixture("graphql_review_threads.json"))
        _register_graphql(responses.mock, _load_fixture("graphql_resolve_ok.json"))

        pr = self._pr()
        gate = GateResult(
            conclusion="success",
            severity_counts={"error": 0, "warning": 0, "info": 0},
            placed=[],
            inline=[],
            config=ReviewConfig(),
        )

        post_inline_review(
            pr,
            gate,
            in_scope_paths={self.PATH},
            regions_by_path={self.PATH: [(140, 145)]},
            owner=self.OWNER,
            repo=self.REPO,
            resolve_outdated=True,
        )

        assert len(responses.mock.calls) == 2


class TestRenderBodyIncrementalDisclaimer:
    """Gap #5: render_body with scope='incremental' prepends a deterministic disclaimer."""

    def test_incremental_review_section_has_scope_disclaimer(self) -> None:
        """scope='incremental' -> Review section prefixed with deterministic disclaimer."""
        body = render_body(_sample_result(), scope="incremental")
        assert "scoped to files changed since" in body

    def test_incremental_disclaimer_mentions_carried_findings_when_present(self) -> None:
        """scope='incremental' + carried_open_count>0 -> disclaimer mentions carried findings."""
        body = render_body(_sample_result(), scope="incremental", carried_open_count=3)
        assert "scoped to files changed since" in body
        assert "3" in body
        # Must mention that prior findings are carried forward
        assert "carried" in body.lower() or "prior" in body.lower()

    def test_incremental_disclaimer_no_carried_clause_when_zero(self) -> None:
        """Incremental scope with zero carried findings shows disclaimer only."""
        body = render_body(_sample_result(), scope="incremental", carried_open_count=0)
        assert "scoped to files changed since" in body
        # No carried-count mention when zero
        assert "0 prior" not in body
        assert "0 carried" not in body

    def test_full_review_section_has_no_disclaimer(self) -> None:
        """scope='full' -> Review section is engine summary verbatim, no disclaimer."""
        body = render_body(_sample_result(), scope="full")
        assert "scoped to files changed since" not in body

    def test_default_scope_no_disclaimer(self) -> None:
        """scope omitted (default) -> no disclaimer (existing callers unchanged)."""
        body = render_body(_sample_result())
        assert "scoped to files changed since" not in body

    def test_disclaimer_is_deterministic_not_engine_derived(self) -> None:
        """The disclaimer text is constant -- not derived from result.summary_markdown."""
        result1 = ReviewResult(
            summary_markdown="Engine says: one file reviewed.",
            findings=[],
            engine_meta={"model": "m1", "duration_s": 0.1},
        )
        result2 = ReviewResult(
            summary_markdown="Engine says: three files in scope.",
            findings=[],
            engine_meta={"model": "m2", "duration_s": 0.2},
        )
        body1 = render_body(result1, scope="incremental")
        body2 = render_body(result2, scope="incremental")
        # Both bodies share the same disclaimer prefix (deterministic)
        assert "scoped to files changed since" in body1
        assert "scoped to files changed since" in body2
