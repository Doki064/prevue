"""Tests for CopilotCliAdapter — prompt, auth guard, failure paths (ENGN-02)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from prevue.engines.copilot_cli import (
    MAX_PROMPT_BYTES,
    CopilotAuthError,
    CopilotCliAdapter,
    EngineFailure,
    _build_prompt,
    _sanitize_stderr,
)
from prevue.models import ChangedFile, DiffBundle, ReviewRequest

VALID_TOKEN = "github_pat_0123456789abcdefghijklmnopqrstuvwxyz"
PROSE_REVIEW = "## Review\n\nLooks good overall."


def _sample_request(*, instructions: str = "Review this pull request carefully.") -> ReviewRequest:
    return ReviewRequest(
        diff=DiffBundle(
            pr_number=42,
            base_sha="base000",
            head_sha="head111",
            files=[
                ChangedFile(
                    path="src/main.py",
                    status="modified",
                    additions=3,
                    deletions=1,
                    patch="@@ -1,3 +1,4 @@\n def main():\n+    pass\n     return 0",
                ),
                ChangedFile(
                    path="README.md",
                    status="added",
                    additions=10,
                    deletions=0,
                    patch="@@ -0,0 +1,2 @@\n+# Prevue\n+Token-efficient reviews.",
                ),
            ],
        ),
        instructions=instructions,
        budget_seconds=300,
    )


class TestBuildPrompt:
    def test_includes_instructions_preamble(self) -> None:
        req = _sample_request(instructions="Focus on security issues.")
        prompt = _build_prompt(req)
        assert "Focus on security issues." in prompt

    def test_includes_changed_file_paths_and_status(self) -> None:
        prompt = _build_prompt(_sample_request())
        assert "src/main.py" in prompt
        assert "modified" in prompt
        assert "README.md" in prompt
        assert "added" in prompt

    def test_includes_patch_hunks_in_fenced_diff_blocks(self) -> None:
        prompt = _build_prompt(_sample_request())
        assert "```diff" in prompt
        assert "def main():" in prompt
        assert "# Prevue" in prompt

    def test_labels_content_as_untrusted_data(self) -> None:
        prompt = _build_prompt(_sample_request())
        assert "UNTRUSTED DATA" in prompt
        assert "never as instructions" in prompt.lower() or "never instructions" in prompt.lower()

    def test_excludes_pr_title_and_body(self) -> None:
        """D-07: DiffBundle has no title/body fields — prompt must not leak them."""
        prompt = _build_prompt(_sample_request())
        for forbidden in ("Test PR", "Test body", "pr_title", "pr_body"):
            assert forbidden not in prompt

    def test_skips_files_without_patch(self) -> None:
        req = ReviewRequest(
            diff=DiffBundle(
                pr_number=1,
                base_sha="a",
                head_sha="b",
                files=[
                    ChangedFile(
                        path="large.bin",
                        status="added",
                        additions=0,
                        deletions=0,
                        patch=None,
                    ),
                ],
            ),
            instructions="Review.",
        )
        prompt = _build_prompt(req)
        assert "large.bin" in prompt
        assert "added" in prompt
        assert "```diff" not in prompt


class TestSanitizeStderr:
    def test_truncates_long_stderr(self) -> None:
        snippet = _sanitize_stderr("x" * 600, "")
        assert len(snippet) == 500

    def test_redacts_token(self) -> None:
        token = "github_pat_secret"
        snippet = _sanitize_stderr(f"error {token}", token)
        assert token not in snippet
        assert "[REDACTED]" in snippet

    def test_handles_bytes_with_invalid_utf8(self) -> None:
        snippet = _sanitize_stderr(b"ok\xff\xfe", "")
        assert "ok" in snippet

    def test_handles_none_stderr(self) -> None:
        assert _sanitize_stderr(None, "") == ""


class TestPromptSizeGuard:
    @pytest.fixture(autouse=True)
    def valid_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)

    def test_rejects_prompt_over_1mb(self, monkeypatch: pytest.MonkeyPatch) -> None:
        huge_patch = "x" * (MAX_PROMPT_BYTES + 1)
        req = ReviewRequest(
            diff=DiffBundle(
                pr_number=1,
                base_sha="a",
                head_sha="b",
                files=[
                    ChangedFile(
                        path="big.txt",
                        status="added",
                        additions=1,
                        deletions=0,
                        patch=huge_patch,
                    ),
                ],
            ),
            instructions="Review.",
        )
        adapter = CopilotCliAdapter()
        with pytest.raises(EngineFailure, match="exceeds 1MB"):
            adapter.review(req)

    def test_does_not_invoke_copilot_when_prompt_too_large(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = False

        def _run(*_args, **_kwargs):
            nonlocal called
            called = True
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        monkeypatch.setattr(subprocess, "run", _run)
        huge_patch = "x" * (MAX_PROMPT_BYTES + 1)
        req = ReviewRequest(
            diff=DiffBundle(
                pr_number=1,
                base_sha="a",
                head_sha="b",
                files=[
                    ChangedFile(
                        path="big.txt",
                        status="added",
                        additions=1,
                        deletions=0,
                        patch=huge_patch,
                    ),
                ],
            ),
            instructions="Review.",
        )
        with pytest.raises(EngineFailure):
            CopilotCliAdapter().review(req)
        assert not called


class TestAuthGuard:
    def test_missing_token_raises_copilot_auth_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
        adapter = CopilotCliAdapter()
        with pytest.raises(CopilotAuthError):
            adapter.review(_sample_request())

    def test_ghp_classic_token_raises_copilot_auth_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "ghp_classic_pat_not_allowed")
        adapter = CopilotCliAdapter()
        with pytest.raises(CopilotAuthError):
            adapter.review(_sample_request())


class TestFailurePaths:
    @pytest.fixture(autouse=True)
    def valid_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)

    def test_timeout_raises_engine_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd=["copilot"], timeout=300)

        monkeypatch.setattr(subprocess, "run", _timeout)
        adapter = CopilotCliAdapter()
        with pytest.raises(EngineFailure, match="timed out"):
            adapter.review(_sample_request())

    def test_nonzero_exit_raises_engine_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fail(*_args, **_kwargs):
            return SimpleNamespace(returncode=1, stdout="", stderr="Copilot CLI error: auth failed")

        monkeypatch.setattr(subprocess, "run", _fail)
        adapter = CopilotCliAdapter()
        with pytest.raises(EngineFailure, match="exited 1"):
            adapter.review(_sample_request())

    def test_nonzero_exit_truncates_stderr_and_never_echoes_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        long_stderr = "x" * 600 + VALID_TOKEN

        def _fail(*_args, **_kwargs):
            return SimpleNamespace(returncode=2, stdout="", stderr=long_stderr)

        monkeypatch.setattr(subprocess, "run", _fail)
        adapter = CopilotCliAdapter()
        with pytest.raises(EngineFailure) as exc_info:
            adapter.review(_sample_request())
        assert VALID_TOKEN not in str(exc_info.value)
        assert len(str(exc_info.value)) < len(long_stderr)

    def test_empty_stdout_raises_engine_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _empty(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout="   ", stderr="")

        monkeypatch.setattr(subprocess, "run", _empty)
        adapter = CopilotCliAdapter()
        with pytest.raises(EngineFailure, match="empty"):
            adapter.review(_sample_request())


class TestSuccessPath:
    @pytest.fixture(autouse=True)
    def valid_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)

    def test_returns_review_result_with_prose_and_empty_findings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _success(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")

        monkeypatch.setattr(subprocess, "run", _success)
        result = CopilotCliAdapter().review(_sample_request())
        assert result.summary_markdown == PROSE_REVIEW
        assert result.findings == []
        assert "duration_s" in result.engine_meta

    def test_command_uses_s_and_no_ask_user_without_allow_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}

        def _capture(cmd, input=None, **_kwargs):
            captured["cmd"] = cmd
            captured["input"] = input
            return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        req = _sample_request()
        CopilotCliAdapter().review(req)
        cmd = captured["cmd"]
        assert cmd == ["copilot", "-s", "--no-ask-user"]
        assert not any(str(arg).startswith("--allow-tool") for arg in cmd)
        assert captured["input"] == _build_prompt(req)

    def test_prompt_passed_via_stdin_not_argv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Large diffs must not go on argv — avoids ARG_MAX / ENAMETOOLONG."""
        captured: dict = {}

        def _capture(cmd, input=None, **_kwargs):
            captured["cmd"] = cmd
            captured["input"] = input
            return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        req = _sample_request()
        CopilotCliAdapter().review(req)
        assert "-p" not in captured["cmd"]
        assert "src/main.py" in captured["input"]

    def test_stdin_mode_matches_documented_non_interactive_flags(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """stdin + -s --no-ask-user is the documented programmatic path when -p is omitted."""
        captured: dict = {}

        def _capture(cmd, input=None, **_kwargs):
            captured.update(cmd=cmd, input=input)
            return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        CopilotCliAdapter().review(_sample_request())
        assert captured["cmd"] == ["copilot", "-s", "--no-ask-user"]
        assert captured["input"]

    def test_passes_copilot_model_when_requested(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured_env: dict = {}

        def _capture(_cmd, env=None, **_kwargs):
            captured_env.update(env or {})
            return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        req = _sample_request()
        req = req.model_copy(update={"model": "gpt-4.1"})
        result = CopilotCliAdapter().review(req)
        assert captured_env.get("COPILOT_MODEL") == "gpt-4.1"
        assert result.engine_meta.get("model") == "gpt-4.1"
