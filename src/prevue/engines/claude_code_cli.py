"""Claude Code CLI engine adapter (ENGN-04)."""

from __future__ import annotations

import os
import subprocess

from prevue.engines import flow
from prevue.engines.base import EngineAdapter
from prevue.engines.errors import AuthError, EngineFailure, sanitize_stderr
from prevue.engines.prompt import MAX_PROMPT_BYTES, build_prompt
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
            raise EngineFailure(f"Claude Code CLI timed out after {budget_seconds}s") from e

        if proc.returncode != 0:
            raise EngineFailure(
                f"Claude Code CLI exited {proc.returncode}: {sanitize_stderr(proc.stderr, secret)}"
            )

        review_text = proc.stdout.strip()
        if not review_text:
            raise EngineFailure("Claude Code CLI returned empty output")
        return review_text

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
