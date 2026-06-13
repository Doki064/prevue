"""Copilot CLI engine adapter — headless subprocess, zero-tool posture (ENGN-02)."""

from __future__ import annotations

import os
import subprocess

from prevue.engines import flow
from prevue.engines.base import EngineAdapter
from prevue.engines.errors import AuthError, EngineFailure, sanitize_stderr
from prevue.engines.prompt import (
    CLASSIFY_TIMEOUT_SECONDS,
    MAX_PROMPT_BYTES,
    OUTPUT_CONTRACT,
    _build_prompt,
    _build_retry_prompt,
    _escape_line,
    _safe_diff_block,
    build_classify_prompt,
    build_prompt,
    parse_classify_response,
)

__all__ = [
    "CopilotAuthError",
    "CopilotCliAdapter",
    "EngineFailure",
    "MAX_PROMPT_BYTES",
    "OUTPUT_CONTRACT",
    "_build_prompt",
    "_build_retry_prompt",
    "_escape_line",
    "_safe_diff_block",
    "_sanitize_stderr",
    "build_prompt",
]
from prevue.models import ReviewRequest, ReviewResult

# Re-export shims — legacy import sites in tests and downstream code.
_sanitize_stderr = sanitize_stderr


class CopilotAuthError(AuthError):
    """Raised when COPILOT_GITHUB_TOKEN is missing or not a fine-grained PAT."""


class CopilotCliAdapter(EngineAdapter):
    name = "copilot-cli"

    def _invoke(
        self,
        prompt: str,
        env: dict[str, str],
        token: str,
        budget_seconds: int,
    ) -> str:
        cmd = ["copilot", "-s", "--no-ask-user"]
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                env=env,
                capture_output=True,
                text=True,
                timeout=budget_seconds,
            )
        except subprocess.TimeoutExpired as e:
            raise EngineFailure(f"Copilot CLI timed out after {budget_seconds}s") from e

        if proc.returncode != 0:
            raise EngineFailure(
                f"Copilot CLI exited {proc.returncode}: {sanitize_stderr(proc.stderr, token)}"
            )

        review_text = proc.stdout.strip()
        if not review_text:
            raise EngineFailure("Copilot CLI returned empty output")
        return review_text

    def review(self, req: ReviewRequest) -> ReviewResult:
        token = os.environ.get("COPILOT_GITHUB_TOKEN", "")
        if not token.startswith("github_pat_"):
            raise CopilotAuthError(
                "COPILOT_GITHUB_TOKEN must be a fine-grained, user-owned PAT "
                "(github_pat_…) with the Copilot Requests permission."
            )

        env = {**os.environ, "COPILOT_GITHUB_TOKEN": token}
        if req.model:
            env["COPILOT_MODEL"] = req.model

        return flow.review_with_retry(
            req,
            invoke=lambda p: self._invoke(p, env, token, req.budget_seconds),
            secret=token,
            build_prompt=build_prompt,
            max_prompt_bytes=MAX_PROMPT_BYTES,
            model_label=req.model or "default",
        )

    def classify(
        self,
        paths: list[str],
        allowed_labels: tuple[str, ...] | list[str],
        *,
        model: str | None = None,
    ) -> dict[str, str]:
        token = os.environ.get("COPILOT_GITHUB_TOKEN", "")
        if not token.startswith("github_pat_"):
            raise CopilotAuthError(
                "COPILOT_GITHUB_TOKEN must be a fine-grained, user-owned PAT "
                "(github_pat_…) with the Copilot Requests permission."
            )

        env = {**os.environ, "COPILOT_GITHUB_TOKEN": token}
        if model:
            env["COPILOT_MODEL"] = model

        prompt = build_classify_prompt(paths, allowed_labels)
        text = self._invoke(prompt, env, token, CLASSIFY_TIMEOUT_SECONDS)
        return parse_classify_response(text, paths, allowed_labels)
