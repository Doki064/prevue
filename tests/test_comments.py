"""Tests for sticky PR comment upsert."""

from __future__ import annotations

from unittest.mock import MagicMock

from prevue.classify.models import ClassificationResult
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
    MARKER,
    _escape_inline_markdown,
    _escape_table_cell,
    _is_prevue_sticky,
    _safe_suggestion_block,
    post_inline_review,
    render_body,
    render_inline_comment,
    upsert_skip_note,
    upsert_sticky,
)
from prevue.models import Finding, ReviewResult


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

        assert post_inline_review(pr, gate) is True

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

        assert post_inline_review(pr, gate) is True
        pr.create_review.assert_not_called()

    def test_swallows_github_exception(self, capsys) -> None:
        from github import GithubException

        gate = self._gate([self._finding()])
        pr = MagicMock()
        pr.get_review_comments.return_value = []
        pr.create_review.side_effect = GithubException(422, {"message": "Validation Failed"}, None)

        assert post_inline_review(pr, gate) is False
        err = capsys.readouterr().err
        assert "inline review POST failed" in err
        assert "1 comment" in err

    def test_updates_existing_inline_at_same_location(self) -> None:
        finding = self._finding(path="a.py", line=1, title="Updated")
        gate = self._gate([finding])
        existing = MagicMock()
        existing.path = "a.py"
        existing.line = 1
        existing.side = "RIGHT"
        existing.body = "old\n\n<sub>posted by Prevue</sub>"
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]

        assert post_inline_review(pr, gate) is True

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
        existing.body = "old\n\n<sub>posted by Prevue</sub>"
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]

        assert post_inline_review(pr, gate) is True

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

        assert post_inline_review(pr, gate) is True

        pr.create_review.assert_not_called()
        stale.delete.assert_called_once()

    def test_create_failure_skips_stale_delete(self) -> None:
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

        assert post_inline_review(pr, gate) is False

        stale.delete.assert_not_called()

    def test_create_failure_skips_existing_inline_edit(self) -> None:
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
        existing.body = "old\n\n<sub>posted by Prevue</sub>"
        existing.user.login = "github-actions[bot]"
        pr = MagicMock()
        pr.get_review_comments.return_value = [existing]
        pr.create_review.side_effect = GithubException(422, {"message": "Validation Failed"}, None)

        assert post_inline_review(pr, gate) is False

        pr.create_review.assert_called_once()
        existing.edit.assert_not_called()

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

        assert post_inline_review(pr, gate) is True

        pr.create_review.assert_called_once()
        stale.delete.assert_called_once()


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
        metadata_idx = body.index("### Metadata")
        assert verdict_idx < review_idx < findings_idx < metadata_idx
        assert body.index("<details>") > findings_idx

    def test_verdict_mirrors_gate_helpers(self) -> None:
        gate = self._gate()
        body = render_body(_sample_result(), gate=gate)

        assert verdict_title(gate) in body
        assert severity_counts_line(gate) in body
        assert thresholds_line(gate) in body

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

        assert body.count("<details>") == 2
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
        assert rendered.endswith("<sub>posted by Prevue</sub>")

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
