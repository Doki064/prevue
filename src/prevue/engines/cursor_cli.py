"""Cursor CLI engine adapter (ENGN-04)."""

from __future__ import annotations

import os
import subprocess
import tempfile

from prevue.engines import flow
from prevue.engines.base import EngineAdapter
from prevue.engines.errors import AuthError, EngineFailure, sanitize_stderr
from prevue.engines.prompt import MAX_PROMPT_BYTES, build_prompt
from prevue.models import ReviewRequest, ReviewResult


class CursorAuthError(AuthError):
    """Raised when CURSOR_API_KEY is missing."""


class CursorAdapter(EngineAdapter):
    name = "cursor-cli"

    def _invoke(
        self,
        prompt: str,
        env: dict[str, str],
        secret: str,
        budget_seconds: int,
        model: str | None,
    ) -> str:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmp_path = tmp.name
        try:
            tmp.write(prompt)
            tmp.close()
            cmd = ["cursor-agent", "-p", "--output-format", "text", "-f", tmp_path]
            if model:
                cmd.extend(["-m", model])
            try:
                proc = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=budget_seconds,
                )
            except subprocess.TimeoutExpired as e:
                raise EngineFailure(
                    f"Cursor CLI timed out after {budget_seconds}s"
                ) from e

            if proc.returncode != 0:
                raise EngineFailure(
                    f"Cursor CLI exited {proc.returncode}: "
                    f"{sanitize_stderr(proc.stderr, secret)}"
                )

            review_text = proc.stdout.strip()
            if not review_text:
                raise EngineFailure("Cursor CLI returned empty output")
            return review_text
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def review(self, req: ReviewRequest) -> ReviewResult:
        key = os.environ.get("CURSOR_API_KEY", "")
        if not key:
            raise CursorAuthError("CURSOR_API_KEY is not set.")

        env = {**os.environ, "CURSOR_API_KEY": key}
        return flow.review_with_retry(
            req,
            invoke=lambda p: self._invoke(p, env, key, req.budget_seconds, req.model),
            secret=key,
            build_prompt=build_prompt,
            max_prompt_bytes=MAX_PROMPT_BYTES,
            model_label=req.model or "default",
        )
