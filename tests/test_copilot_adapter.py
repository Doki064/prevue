"""Tests for the copilot-cli CliEngineAdapter — prompt, auth guard, failure paths (ENGN-02)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from prevue.engines.errors import CopilotAuthError, EngineFailure, sanitize_stderr
from prevue.engines.prompt import MAX_PROMPT_BYTES, OUTPUT_CONTRACT, _build_prompt
from prevue.engines.registry import get_adapter
from prevue.models import ChangedFile, DiffBundle, ReviewRequest
from tests.engine_helpers import (
    PROSE_REVIEW,
    VALID_FINDING,
    VALID_TOKEN,
    make_sample_request,
    stdout_with_fence,
)

_sample_request = make_sample_request
_stdout_with_fence = stdout_with_fence


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
        snippet = sanitize_stderr("x" * 600, "")
        assert len(snippet) == 500

    def test_redacts_token(self) -> None:
        token = "github_pat_secret"
        snippet = sanitize_stderr(f"error {token}", token)
        assert token not in snippet
        assert "[REDACTED]" in snippet

    def test_redacts_token_split_by_old_truncation_boundary(self) -> None:
        token = "github_pat_" + "x" * 82  # 93 chars
        trailing = "y" * 450  # >500 chars follow the token start, forcing the boundary
        stderr = f"prefix {token}{trailing}"
        snippet = sanitize_stderr(stderr, token)
        assert token not in snippet
        # also assert no *substring* of the token longer than a few chars leaks
        assert not any(token[i : i + 20] in snippet for i in range(0, len(token) - 20, 20))

    def test_handles_bytes_with_invalid_utf8(self) -> None:
        snippet = sanitize_stderr(b"ok\xff\xfe", "")
        assert "ok" in snippet

    def test_handles_none_stderr(self) -> None:
        assert sanitize_stderr(None, "") == ""


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
        adapter = get_adapter("copilot-cli")
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
            get_adapter("copilot-cli").review(req)
        assert not called


class TestAuthGuard:
    def test_missing_token_raises_copilot_auth_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
        adapter = get_adapter("copilot-cli")
        with pytest.raises(CopilotAuthError):
            adapter.review(_sample_request())

    def test_ghp_classic_token_raises_copilot_auth_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "ghp_classic_pat_not_allowed")
        adapter = get_adapter("copilot-cli")
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
        adapter = get_adapter("copilot-cli")
        with pytest.raises(EngineFailure, match="timed out"):
            adapter.review(_sample_request())

    def test_nonzero_exit_raises_engine_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fail(*_args, **_kwargs):
            return SimpleNamespace(returncode=1, stdout="", stderr="Copilot CLI error: auth failed")

        monkeypatch.setattr(subprocess, "run", _fail)
        adapter = get_adapter("copilot-cli")
        with pytest.raises(EngineFailure, match="exited 1"):
            adapter.review(_sample_request())

    def test_nonzero_exit_truncates_stderr_and_never_echoes_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        long_stderr = "x" * 600 + VALID_TOKEN

        def _fail(*_args, **_kwargs):
            return SimpleNamespace(returncode=2, stdout="", stderr=long_stderr)

        monkeypatch.setattr(subprocess, "run", _fail)
        adapter = get_adapter("copilot-cli")
        with pytest.raises(EngineFailure) as exc_info:
            adapter.review(_sample_request())
        assert VALID_TOKEN not in str(exc_info.value)
        assert len(str(exc_info.value)) < len(long_stderr)

    def test_nonzero_exit_includes_stdout_in_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fail(*_args, **_kwargs):
            return SimpleNamespace(returncode=1, stdout="engine error: bad request", stderr="")

        monkeypatch.setattr(subprocess, "run", _fail)
        adapter = get_adapter("copilot-cli")
        with pytest.raises(EngineFailure, match="engine error: bad request"):
            adapter.review(_sample_request())

    def test_nonzero_exit_redacts_token_from_stdout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fail(*_args, **_kwargs):
            return SimpleNamespace(returncode=1, stdout=f"leaked: {VALID_TOKEN}", stderr="")

        monkeypatch.setattr(subprocess, "run", _fail)
        adapter = get_adapter("copilot-cli")
        with pytest.raises(EngineFailure) as exc_info:
            adapter.review(_sample_request())
        assert VALID_TOKEN not in str(exc_info.value)

    def test_empty_stdout_raises_engine_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _empty(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout="   ", stderr="")

        monkeypatch.setattr(subprocess, "run", _empty)
        adapter = get_adapter("copilot-cli")
        with pytest.raises(EngineFailure, match="empty"):
            adapter.review(_sample_request())


class TestOutputContract:
    def test_output_contract_constant_has_rubric_and_fence_instruction(self) -> None:
        assert "error" in OUTPUT_CONTRACT
        assert "warning" in OUTPUT_CONTRACT
        assert "info" in OUTPUT_CONTRACT
        assert "RIGHT" in OUTPUT_CONTRACT
        assert "LEFT" in OUTPUT_CONTRACT
        assert "last element" in OUTPUT_CONTRACT.lower()

    def test_prompt_places_contract_before_untrusted_data(self) -> None:
        prompt = _build_prompt(_sample_request())
        contract_line = next(line for line in OUTPUT_CONTRACT.splitlines() if line.strip())
        contract_idx = prompt.index(contract_line[: min(20, len(contract_line))])
        untrusted_idx = prompt.index("UNTRUSTED DATA")
        assert contract_idx < untrusted_idx

    def test_prompt_includes_severity_rubric_and_fence_at_end_instruction(self) -> None:
        prompt = _build_prompt(_sample_request())
        assert "error" in prompt
        assert "warning" in prompt
        assert "info" in prompt
        lower = prompt.lower()
        assert "json" in lower
        assert "last" in lower

    def test_captured_review_prompt_carries_contract_via_argv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The default sample prompt is well under the argv ceiling, so it is
        delivered via `-p <prompt>` (reaching Copilot's OTEL-emitting code path),
        not stdin."""
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)
        captured: dict = {}

        def _capture(cmd, input=None, **_kwargs):
            captured["cmd"] = cmd
            captured["input"] = input
            return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        get_adapter("copilot-cli").review(_sample_request())
        assert captured["input"] is None
        cmd = captured["cmd"]
        prompt = cmd[cmd.index("-p") + 1]
        assert "Clear, Concise, Correct, Complete" in prompt
        assert prompt.index("Clear") < prompt.index("UNTRUSTED DATA")


class TestRetryThenDegrade:
    @pytest.fixture(autouse=True)
    def valid_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)

    def test_valid_fence_returns_findings_and_strips_fence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stdout = _stdout_with_fence(payload=[VALID_FINDING])

        def _success(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

        monkeypatch.setattr(subprocess, "run", _success)
        result = get_adapter("copilot-cli").review(_sample_request())
        assert result.degraded is False
        assert len(result.findings) == 1
        assert result.findings[0].path == "src/main.py"
        assert result.summary_markdown == PROSE_REVIEW
        assert result.engine_meta.get("retried") is False

    def test_bad_fence_then_good_retry_sets_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str | None] = []

        def _run(cmd, input=None, **_kwargs):
            # Small sample prompt fits under argv_prompt_max_bytes: delivered via
            # -p, so `input` is None — capture from cmd instead (10-10 gap closure).
            cmd_list = list(cmd)
            prompt_content = input if input is not None else cmd_list[cmd_list.index("-p") + 1]
            calls.append(prompt_content)
            if len(calls) == 1:
                stdout = PROSE_REVIEW
            else:
                stdout = _stdout_with_fence(payload=[VALID_FINDING])
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

        monkeypatch.setattr(subprocess, "run", _run)
        result = get_adapter("copilot-cli").review(_sample_request())
        assert len(calls) == 2
        assert calls[1] is not None
        assert "fence" in calls[1].lower() or "parse" in calls[1].lower()
        assert result.degraded is False
        assert len(result.findings) == 1
        assert result.engine_meta.get("retried") is True

    def test_both_bad_fence_degrades_without_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _run(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")

        monkeypatch.setattr(subprocess, "run", _run)
        result = get_adapter("copilot-cli").review(_sample_request())
        assert result.degraded is True
        assert result.findings == []
        assert PROSE_REVIEW in result.summary_markdown
        assert "parse_error" in result.engine_meta

    def test_all_invalid_findings_degrades_with_dropped_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        invalid = [{**VALID_FINDING, "severity": "critical"}]
        stdout = _stdout_with_fence(payload=invalid)

        def _success(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

        monkeypatch.setattr(subprocess, "run", _success)
        result = get_adapter("copilot-cli").review(_sample_request())
        assert result.degraded is True
        assert result.findings == []
        assert result.dropped_findings == 1

    def test_mixed_salvage_keeps_valid_not_degraded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = [VALID_FINDING, {**VALID_FINDING, "severity": "nope"}]
        stdout = _stdout_with_fence(payload=payload)

        def _success(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

        monkeypatch.setattr(subprocess, "run", _success)
        result = get_adapter("copilot-cli").review(_sample_request())
        assert result.degraded is False
        assert len(result.findings) == 1
        assert result.dropped_findings == 1

    def test_retry_skipped_when_retry_prompt_exceeds_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import prevue.engines.prompt as prompt_module

        prompt = _build_prompt(_sample_request())
        small_limit = len(prompt.encode("utf-8")) + 50
        # Patch the source module used by CliEngineAdapter (cli_adapter._prompt_module).
        monkeypatch.setattr(prompt_module, "MAX_PROMPT_BYTES", small_limit)
        call_count = 0

        def _run(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")

        monkeypatch.setattr(subprocess, "run", _run)
        result = get_adapter("copilot-cli").review(_sample_request())
        assert call_count == 1
        assert result.degraded is True
        assert result.findings == []

    def test_hard_failure_on_retry_degrades_with_first_prose(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        call_count = 0

        def _run(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")
            raise subprocess.TimeoutExpired(cmd=["copilot"], timeout=300)

        monkeypatch.setattr(subprocess, "run", _run)
        result = get_adapter("copilot-cli").review(_sample_request())
        assert result.degraded is True
        assert result.summary_markdown == PROSE_REVIEW
        assert result.findings == []
        assert result.engine_meta.get("retried") is True


class TestSuccessPath:
    @pytest.fixture(autouse=True)
    def valid_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)

    def test_returns_review_result_with_prose_and_empty_findings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _success(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _success)
        result = get_adapter("copilot-cli").review(_sample_request())
        assert result.summary_markdown == PROSE_REVIEW
        assert result.findings == []
        assert result.degraded is False
        assert "duration_s" in result.engine_meta

    def test_command_uses_s_and_no_ask_user_without_allow_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default sample prompt fits under the argv ceiling: -p carries the prompt,
        nothing is piped to stdin — this is the branch that reaches Copilot's
        OTEL-emitting code path (.planning/debug/copilot-otel-real-capture-recurrence.md)."""
        captured: dict = {}

        def _capture(cmd, input=None, **_kwargs):
            captured["cmd"] = cmd
            captured["input"] = input
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        req = _sample_request()
        get_adapter("copilot-cli").review(req)
        cmd = captured["cmd"]
        assert cmd == ["copilot", "-s", "--no-ask-user", "-p", _build_prompt(req)]
        assert not any(str(arg).startswith("--allow-tool") for arg in cmd)
        assert captured["input"] is None

    def test_oversized_prompt_falls_back_to_stdin_not_argv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Large diffs must not go on argv — avoids ARG_MAX / ENAMETOOLONG (01-07 regression).

        Same argv shape as before this plan: no `-p`, prompt delivered via stdin `input=`.
        """
        spec = get_adapter("copilot-cli")._spec
        ceiling = spec.argv_prompt_max_bytes
        assert ceiling is not None
        huge_patch = "x" * (ceiling + 5_000)  # pushes assembled prompt over the ceiling
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
        captured: dict = {}

        def _capture(cmd, input=None, **_kwargs):
            captured["cmd"] = cmd
            captured["input"] = input
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)
        get_adapter("copilot-cli").review(req)
        assert "-p" not in captured["cmd"]
        assert captured["cmd"] == ["copilot", "-s", "--no-ask-user"]
        assert "big.txt" in captured["input"]

    def test_argv_prompt_max_bytes_boundary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A prompt sized exactly at the ceiling uses -p (inclusive); one byte over falls
        back to stdin."""
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)
        spec = get_adapter("copilot-cli")._spec
        ceiling = spec.argv_prompt_max_bytes
        assert ceiling is not None

        def _request_with_prompt_size(target_bytes: int) -> ReviewRequest:
            req = ReviewRequest(
                diff=DiffBundle(
                    pr_number=1,
                    base_sha="a",
                    head_sha="b",
                    files=[
                        ChangedFile(
                            path="f.txt",
                            status="added",
                            additions=1,
                            deletions=0,
                            patch="x",
                        ),
                    ],
                ),
                instructions="Review.",
            )
            base_len = len(_build_prompt(req).encode("utf-8"))
            pad = max(0, target_bytes - base_len)
            req.diff.files[0].patch = "x" * (1 + pad)
            return req

        captured: dict = {}

        def _capture(cmd, input=None, **_kwargs):
            captured["cmd"] = cmd
            captured["input"] = input
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)

        # At the ceiling (inclusive) -> argv (-p)
        req_at_ceiling = _request_with_prompt_size(ceiling)
        prompt_at_ceiling = _build_prompt(req_at_ceiling)
        assert len(prompt_at_ceiling.encode("utf-8")) <= ceiling
        get_adapter("copilot-cli").review(req_at_ceiling)
        assert "-p" in captured["cmd"]
        assert captured["input"] is None

        # One byte over -> stdin fallback
        req_over = _request_with_prompt_size(ceiling + 1)
        prompt_over = _build_prompt(req_over)
        assert len(prompt_over.encode("utf-8")) > ceiling
        captured.clear()
        get_adapter("copilot-cli").review(req_over)
        assert "-p" not in captured["cmd"]
        assert captured["input"] is not None

    def test_raw_args_still_last_on_both_delivery_branches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ENGN-08/D-10: raw_args land LAST in argv whether the small sample prompt uses
        -p argv delivery or an oversized prompt falls back to stdin."""
        from prevue.engines.cli_adapter import CliEngineAdapter
        from prevue.engines.registry import ENGINES

        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)
        captured: dict = {}

        def _capture(cmd, input=None, **_kwargs):
            captured["cmd"] = cmd
            captured["input"] = input
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        adapter = CliEngineAdapter(ENGINES["copilot-cli"], raw_args=["--extra-flag"])

        # Small prompt -> argv (-p) branch; raw_args still trails
        adapter.review(_sample_request())
        assert captured["cmd"][-1] == "--extra-flag"
        assert "-p" in captured["cmd"]

        # Oversized prompt -> stdin fallback branch; raw_args still trails
        spec = adapter._spec
        ceiling = spec.argv_prompt_max_bytes
        assert ceiling is not None
        huge_patch = "x" * (ceiling + 5_000)
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
        captured.clear()
        adapter.review(req)
        assert captured["cmd"][-1] == "--extra-flag"
        assert "-p" not in captured["cmd"]

    def test_passes_copilot_model_when_requested(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured_env: dict = {}

        def _capture(_cmd, env=None, **_kwargs):
            captured_env.update(env or {})
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        req = _sample_request()
        req = req.model_copy(update={"model": "gpt-4.1"})
        result = get_adapter("copilot-cli").review(req)
        assert captured_env.get("COPILOT_MODEL") == "gpt-4.1"
        assert result.engine_meta.get("model") == "gpt-4.1"


class TestOtelPerCallIsolation:
    """WR-01 (10-boundary-contracts): each review() call gets its own OTEL
    subdirectory under COPILOT_OTEL_FILE_EXPORTER_PATH so multi-call reviews
    (review.max_review_calls > 1) don't re-sum earlier calls' spans."""

    @pytest.fixture(autouse=True)
    def valid_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", VALID_TOKEN)

    def test_two_calls_get_distinct_otel_paths(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        base_otel_dir = str(tmp_path / "copilot-otel")
        monkeypatch.setenv("COPILOT_OTEL_FILE_EXPORTER_PATH", base_otel_dir)
        seen_paths: list[str] = []

        def _capture(_cmd, env=None, **_kwargs):
            seen_paths.append((env or {})["COPILOT_OTEL_FILE_EXPORTER_PATH"])
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        adapter = get_adapter("copilot-cli")
        adapter.review(_sample_request())
        adapter.review(_sample_request())

        assert len(seen_paths) == 2
        assert seen_paths[0] != seen_paths[1]
        import os as _os

        for p in seen_paths:
            # THIRD RECURRENCE regression guard (10-11): the leaf path must
            # never be pre-created on disk (as file or directory) — Copilot's
            # real OTEL file exporter silently no-ops when it already exists.
            assert not _os.path.exists(p)
            assert p.startswith(base_otel_dir)
            assert p.endswith(".jsonl")

    def test_no_base_otel_dir_env_means_no_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
        captured_env: dict = {}

        def _capture(_cmd, env=None, **_kwargs):
            captured_env.update(env or {})
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        get_adapter("copilot-cli").review(_sample_request())
        assert "COPILOT_OTEL_FILE_EXPORTER_PATH" not in captured_env

    def test_makedirs_oserror_degrades_to_job_wide_dir_instead_of_crashing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        """WR-01 (10-boundary-contracts, review pass 3): the except OSError branch
        in review() must degrade otel_path to None (falling back to the job-wide
        dir) rather than let the exception propagate and crash the review.

        10-11 THIRD RECURRENCE fix: tempfile.mkdtemp is no longer called by
        production code, so the OSError-degrade path is now exercised via
        os.makedirs instead."""
        import os as _os

        base_otel_dir = str(tmp_path / "copilot-otel")
        monkeypatch.setenv("COPILOT_OTEL_FILE_EXPORTER_PATH", base_otel_dir)

        def _raise_makedirs(*_args, **_kwargs):
            raise OSError("simulated filesystem failure")

        monkeypatch.setattr(_os, "makedirs", _raise_makedirs)

        captured_env: dict = {}

        def _capture(_cmd, env=None, **_kwargs):
            captured_env.update(env or {})
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _capture)
        adapter = get_adapter("copilot-cli")
        result = adapter.review(_sample_request())

        # Degrades to the job-wide dir (the unscoped env value), not a per-call
        # subdirectory — review() must not crash on the OSError.
        assert captured_env.get("COPILOT_OTEL_FILE_EXPORTER_PATH") == base_otel_dir
        assert result.engine_meta.get("tokens", {}).get("estimated") is True

    def test_retry_gets_distinct_otel_path_with_real_capture(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        """WR-T11 + IN-T05: first and retry invocations of ONE call must each
        get a fresh, distinct OTEL path — reusing one path silently degraded
        the retry's real capture to a ~est estimate (Copilot's file exporter
        no-ops when its configured path already exists)."""
        import json as _json

        base_otel_dir = str(tmp_path / "copilot-otel")
        monkeypatch.setenv("COPILOT_OTEL_FILE_EXPORTER_PATH", base_otel_dir)
        seen_paths: list[str] = []

        def _run(cmd, env=None, **_kwargs):
            path = (env or {})["COPILOT_OTEL_FILE_EXPORTER_PATH"]
            seen_paths.append(path)
            import os as _os

            _os.makedirs(_os.path.dirname(path), exist_ok=True)
            if len(seen_paths) == 1:
                span = {
                    "type": "span",
                    "attributes": {
                        "gen_ai.usage.input_tokens": 1000,
                        "gen_ai.usage.output_tokens": 200,
                    },
                }
                with open(path, "w") as f:
                    f.write(_json.dumps(span) + "\n")
                return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")
            span = {
                "type": "span",
                "attributes": {
                    "gen_ai.usage.input_tokens": 300,
                    "gen_ai.usage.output_tokens": 80,
                },
            }
            with open(path, "w") as f:
                f.write(_json.dumps(span) + "\n")
            return SimpleNamespace(
                returncode=0, stdout=_stdout_with_fence(payload=[VALID_FINDING]), stderr=""
            )

        monkeypatch.setattr(subprocess, "run", _run)
        result = get_adapter("copilot-cli").review(_sample_request())

        assert len(seen_paths) == 2
        assert seen_paths[0] != seen_paths[1]
        assert not seen_paths[0].startswith(seen_paths[1])
        assert not seen_paths[1].startswith(seen_paths[0])

        tokens = result.engine_meta["tokens"]
        assert tokens["estimated"] is False
        assert tokens["input"] == 1300
        assert tokens["output"] == 280

    def test_second_calls_makedirs_oserror_degrade_ignores_sibling_calls_real_spans(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        """WR-T12: a `makedirs` OSError degrade on a LATER call in a multi-call
        job must not sum an earlier call's real span file — the earlier span
        is nested under its own per-attempt subdirectory (WR-T13), so a
        directory-level glob of the job-wide dir can never see it."""
        import json as _json
        import os as _os

        base_otel_dir = str(tmp_path / "copilot-otel")
        monkeypatch.setenv("COPILOT_OTEL_FILE_EXPORTER_PATH", base_otel_dir)

        def _run_success(cmd, env=None, **_kwargs):
            path = (env or {})["COPILOT_OTEL_FILE_EXPORTER_PATH"]
            _os.makedirs(_os.path.dirname(path), exist_ok=True)
            span = {
                "type": "span",
                "attributes": {
                    "gen_ai.usage.input_tokens": 5000,
                    "gen_ai.usage.output_tokens": 900,
                },
            }
            with open(path, "w") as f:
                f.write(_json.dumps(span) + "\n")
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _run_success)
        adapter = get_adapter("copilot-cli")
        first_result = adapter.review(_sample_request())
        assert first_result.engine_meta["tokens"]["estimated"] is False

        real_makedirs = _os.makedirs

        def _raise_makedirs(path, *args, **kwargs):
            if _os.path.abspath(path) == _os.path.abspath(base_otel_dir):
                return real_makedirs(path, *args, **kwargs)
            raise OSError("simulated filesystem failure")

        monkeypatch.setattr(_os, "makedirs", _raise_makedirs)

        def _run_no_span(_cmd, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=_stdout_with_fence(), stderr="")

        monkeypatch.setattr(subprocess, "run", _run_no_span)
        second_result = adapter.review(_sample_request())

        tokens = second_result.engine_meta["tokens"]
        assert tokens["estimated"] is True
        assert tokens.get("input", 0) < 5000
