"""Copilot CLI engine adapter — headless subprocess, zero-tool posture (ENGN-02)."""

from __future__ import annotations

import os

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
from prevue.engines.subprocess_invoke import invoke_subprocess_text
from prevue.models import ReviewRequest, ReviewResult

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
        return invoke_subprocess_text(
            ["copilot", "-s", "--no-ask-user"],
            env=env,
            secret=token,
            budget_seconds=budget_seconds,
            cli_label="Copilot CLI",
            input_text=prompt,
        )

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
