"""Claude Code CLI engine adapter (ENGN-04)."""

from __future__ import annotations

import os

from prevue.engines import flow
from prevue.engines.base import EngineAdapter
from prevue.engines.errors import AuthError
from prevue.engines.prompt import (
    CLASSIFY_TIMEOUT_SECONDS,
    MAX_PROMPT_BYTES,
    build_classify_prompt,
    build_prompt,
    parse_classify_response,
)
from prevue.engines.subprocess_invoke import invoke_subprocess_text
from prevue.models import ReviewRequest, ReviewResult


class ClaudeAuthError(AuthError):
    """Raised when ANTHROPIC_API_KEY is missing."""


class ClaudeCodeAdapter(EngineAdapter):
    name = "claude-code-cli"

    def _invoke(
        self,
        prompt: str,
        env: dict[str, str],
        secret: str,
        budget_seconds: int,
        model: str | None,
    ) -> str:
        cmd = ["claude", "--bare", "-p", "--output-format", "text"]
        if model:
            cmd.extend(["--model", model])
        return invoke_subprocess_text(
            cmd,
            env=env,
            secret=secret,
            budget_seconds=budget_seconds,
            cli_label="Claude Code CLI",
            input_text=prompt,
        )

    def review(self, req: ReviewRequest) -> ReviewResult:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ClaudeAuthError("ANTHROPIC_API_KEY is not set.")

        env = {**os.environ, "ANTHROPIC_API_KEY": key}
        return flow.review_with_retry(
            req,
            invoke=lambda p: self._invoke(p, env, key, req.budget_seconds, req.model),
            secret=key,
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
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ClaudeAuthError("ANTHROPIC_API_KEY is not set.")

        env = {**os.environ, "ANTHROPIC_API_KEY": key}
        prompt = build_classify_prompt(paths, allowed_labels)
        text = self._invoke(prompt, env, key, CLASSIFY_TIMEOUT_SECONDS, model)
        return parse_classify_response(text, paths, allowed_labels)
