"""Behavioral tests for repository_dispatch gate revalidation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prevue.commands import needs_engine_for_body
from prevue.gate_validate import (
    DispatchPayload,
    GateValidationError,
    materialize_comment_event,
    run_gate_revalidate,
    validate_command_dispatch,
)

FP16 = "abc123def4567890"
HEAD_SHA = "abc123def456789012345678901234567890abcd"
BASE_SHA = "base000def456789012345678901234567890abcd"
FRAMEWORK_SHA = "framework0000000000000000000000000000000000"
REPO = "owner/prevue"
ISSUE_NUMBER = "42"
COMMENT_ID = "999"


def _payload(**overrides: object) -> DispatchPayload:
    defaults = {
        "issue_number": ISSUE_NUMBER,
        "head_sha": HEAD_SHA,
        "base_sha": BASE_SHA,
        "framework_sha": FRAMEWORK_SHA,
        "comment_body": "/prevue review",
        "comment_author": "alice",
        "comment_author_association": "MEMBER",
        "comment_id": COMMENT_ID,
        "needs_engine": True,
        "engine": "copilot-cli",
    }
    defaults.update(overrides)
    return DispatchPayload.model_validate(defaults)


def _pull(*, head_repo: str = REPO) -> MagicMock:
    pull = MagicMock()
    pull.head.sha = HEAD_SHA
    pull.base.sha = BASE_SHA
    pull.head.repo.full_name = head_repo
    pull.base.repo = MagicMock()
    return pull


def _comment(**overrides: object) -> MagicMock:
    comment = MagicMock()
    comment.issue_url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}"
    comment.author_association = "MEMBER"
    comment.body = "/prevue review"
    comment.user.login = "alice"
    for key, value in overrides.items():
        setattr(comment, key, value)
    return comment


class TestNeedsEngineForBody:
    def test_review_requires_engine(self) -> None:
        assert needs_engine_for_body("/prevue review") is True

    def test_dismiss_does_not_require_engine(self) -> None:
        assert needs_engine_for_body(f"/prevue dismiss {FP16}") is False

    def test_fenced_review_ignored_for_needs_engine(self) -> None:
        body = """```
/prevue review
```
/prevue dismiss abc123def4567890"""
        assert needs_engine_for_body(body) is False


class TestValidateCommandDispatch:
    def test_accepts_matching_payload(self) -> None:
        with patch("prevue.gate_validate.authorize_commenter", return_value=True):
            validate_command_dispatch(
                payload=_payload(),
                pull=_pull(),
                comment=_comment(),
                expected_engine="copilot-cli",
                framework_sha=FRAMEWORK_SHA,
                repository=REPO,
            )

    def test_rejects_head_sha_mismatch(self) -> None:
        pull = _pull()
        pull.head.sha = "deadbeef" * 5
        with pytest.raises(GateValidationError, match="head SHA"):
            validate_command_dispatch(
                payload=_payload(),
                pull=pull,
                comment=_comment(),
                expected_engine="copilot-cli",
                framework_sha=FRAMEWORK_SHA,
                repository=REPO,
            )

    def test_rejects_base_sha_mismatch(self) -> None:
        pull = _pull()
        pull.base.sha = "deadbeef" * 5
        with pytest.raises(GateValidationError, match="base SHA"):
            validate_command_dispatch(
                payload=_payload(),
                pull=pull,
                comment=_comment(),
                expected_engine="copilot-cli",
                framework_sha=FRAMEWORK_SHA,
                repository=REPO,
            )

    def test_rejects_fork_pr(self) -> None:
        with pytest.raises(GateValidationError, match="Fork PR"):
            validate_command_dispatch(
                payload=_payload(),
                pull=_pull(head_repo="forker/prevue"),
                comment=_comment(),
                expected_engine="copilot-cli",
                framework_sha=FRAMEWORK_SHA,
                repository=REPO,
            )

    def test_rejects_framework_sha_mismatch(self) -> None:
        with pytest.raises(GateValidationError, match="Framework SHA"):
            validate_command_dispatch(
                payload=_payload(),
                pull=_pull(),
                comment=_comment(),
                expected_engine="copilot-cli",
                framework_sha="other" * 10,
                repository=REPO,
            )

    def test_rejects_comment_body_mismatch(self) -> None:
        with patch("prevue.gate_validate.authorize_commenter", return_value=True):
            with pytest.raises(GateValidationError, match="Comment body"):
                validate_command_dispatch(
                    payload=_payload(),
                    pull=_pull(),
                    comment=_comment(body="/prevue review tampered"),
                    expected_engine="copilot-cli",
                    framework_sha=FRAMEWORK_SHA,
                    repository=REPO,
                )

    def test_rejects_association_drift(self) -> None:
        with patch("prevue.gate_validate.authorize_commenter", return_value=True):
            with pytest.raises(GateValidationError, match="association does not match"):
                validate_command_dispatch(
                    payload=_payload(comment_author_association="OWNER"),
                    pull=_pull(),
                    comment=_comment(author_association="MEMBER"),
                    expected_engine="copilot-cli",
                    framework_sha=FRAMEWORK_SHA,
                    repository=REPO,
                )

    def test_rejects_needs_engine_mismatch_fence_aware(self) -> None:
        body = """```
/prevue dismiss abc123def4567890
```
/prevue review"""
        with patch("prevue.gate_validate.authorize_commenter", return_value=True):
            with pytest.raises(GateValidationError, match="needs_engine"):
                validate_command_dispatch(
                    payload=_payload(comment_body=body, needs_engine=False),
                    pull=_pull(),
                    comment=_comment(body=body),
                    expected_engine="copilot-cli",
                    framework_sha=FRAMEWORK_SHA,
                    repository=REPO,
                )

    def test_rejects_engine_mismatch(self) -> None:
        with patch("prevue.gate_validate.authorize_commenter", return_value=True):
            with pytest.raises(GateValidationError, match="Engine does not match"):
                validate_command_dispatch(
                    payload=_payload(engine="copilot-cli"),
                    pull=_pull(),
                    comment=_comment(),
                    expected_engine="claude-code-cli",
                    framework_sha=FRAMEWORK_SHA,
                    repository=REPO,
                )

    def test_rejects_untrusted_association(self) -> None:
        with patch("prevue.gate_validate.authorize_commenter", return_value=True):
            with pytest.raises(GateValidationError, match="association is not trusted"):
                validate_command_dispatch(
                    payload=_payload(comment_author_association="NONE"),
                    pull=_pull(),
                    comment=_comment(author_association="NONE"),
                    expected_engine="copilot-cli",
                    framework_sha=FRAMEWORK_SHA,
                    repository=REPO,
                )


class TestMaterializeCommentEvent:
    def test_writes_issue_comment_shape(self, tmp_path: Path) -> None:
        path = tmp_path / "issue_comment.json"
        materialize_comment_event(
            issue_number=42,
            comment_body="/prevue review",
            comment_author="alice",
            comment_author_association="MEMBER",
            output_path=path,
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["issue"]["number"] == 42
        assert payload["comment"]["body"] == "/prevue review"
        assert payload["comment"]["user"]["login"] == "alice"
        assert payload["comment"]["author_association"] == "MEMBER"

    def test_cli_reads_body_from_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        body_path = tmp_path / "comment.txt"
        body_path.write_text("/prevue review", encoding="utf-8")
        out_path = tmp_path / "issue_comment.json"
        monkeypatch.setenv("PREVUE_ISSUE_NUMBER", "42")
        monkeypatch.setenv("PREVUE_COMMENT_BODY_PATH", str(body_path))
        monkeypatch.setenv("PREVUE_COMMENT_AUTHOR", "alice")
        monkeypatch.setenv("PREVUE_COMMENT_AUTHOR_ASSOCIATION", "MEMBER")
        monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
        from prevue.gate_validate import run_materialize_comment_event

        assert run_materialize_comment_event() == 0
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["comment"]["body"] == "/prevue review"


class TestRunGateRevalidate:
    def test_cli_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        event_path = tmp_path / "event.json"
        event_path.write_text(
            json.dumps({"client_payload": _payload().model_dump()}),
            encoding="utf-8",
        )
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
        monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
        monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
        monkeypatch.setenv("PREVUE_ENGINE", "copilot-cli")
        monkeypatch.setenv("PREVUE_REF", "main")

        mock_comment = _comment()
        mock_pull = _pull()
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pull
        mock_repo.get_issue.return_value.get_comment.return_value = mock_comment

        with (
            patch("prevue.gate_validate.Github") as mock_github,
            patch("prevue.gate_validate.resolve_framework_sha", return_value=FRAMEWORK_SHA),
            patch("prevue.gate_validate.authorize_commenter", return_value=True),
        ):
            mock_github.return_value.get_repo.return_value = mock_repo
            assert run_gate_revalidate() == 0

    def test_cli_failure_prints_and_exits_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        event_path = tmp_path / "event.json"
        event_path.write_text(
            json.dumps({"client_payload": _payload().model_dump()}),
            encoding="utf-8",
        )
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
        monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
        monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")

        mock_pull = _pull()
        mock_pull.head.sha = "mismatch" * 8
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pull
        mock_repo.get_issue.return_value.get_comment.return_value = _comment()

        with (
            patch("prevue.gate_validate.Github") as mock_github,
            patch("prevue.gate_validate.resolve_framework_sha", return_value=FRAMEWORK_SHA),
        ):
            mock_github.return_value.get_repo.return_value = mock_repo
            assert run_gate_revalidate() == 1
