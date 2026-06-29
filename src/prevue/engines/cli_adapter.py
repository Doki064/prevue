"""Generic CLI engine adapter driven by CliEngineSpec (ENGN-10, D-01).

One concrete adapter implements review/classify/classify_skills for ALL CLI engines.
Adding a CLI engine = one CliEngineSpec data entry in spec.py; no subclass needed.
"""

from __future__ import annotations

import os
import tempfile

from prevue.engines import flow
from prevue.engines.base import EngineAdapter
import prevue.engines.prompt as _prompt_module
from prevue.engines.prompt import (
    CLASSIFY_TIMEOUT_SECONDS,
    build_classify_prompt,
    build_prompt,
    build_skill_select_prompt,
    parse_classify_response,
)
from prevue.engines.spec import CliEngineSpec
from prevue.engines.subprocess_invoke import invoke_subprocess_text
from prevue.models import ReviewRequest, ReviewResult


class CliEngineAdapter(EngineAdapter):
    """Single generic CLI engine adapter parameterized by a CliEngineSpec.

    All CLI engines (copilot, claude-code, cursor, antigravity) share this implementation.
    Per-engine variation is captured declaratively in CliEngineSpec (spec.py).
    """

    def __init__(self, spec: CliEngineSpec) -> None:
        self._spec = spec
        self.name = spec.name

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_env(self, model: str | None) -> tuple[str, dict[str, str]]:
        """Validate secret, build subprocess env. Raises spec.auth_error on failure."""
        spec = self._spec
        raw_token = os.environ.get(spec.secret_env, "")
        # validate_secret raises spec.auth_error if invalid; returns token on success
        token = spec.validate_secret(raw_token)
        env = {**os.environ, spec.secret_env: token}
        # Model via env var (e.g. COPILOT_MODEL for copilot-cli)
        if spec.model_flag == "env" and model and spec.model_env:
            env[spec.model_env] = model
        return token, env

    def _invoke(
        self,
        prompt: str,
        env: dict[str, str],
        token: str,
        budget_seconds: int,
        model: str | None,
    ) -> str:
        """Assemble argv + invoke subprocess per spec configuration."""
        spec = self._spec
        cmd = list(spec.base_argv)

        # Determine cwd for cursor-style adapters
        cwd: str | None = None
        if spec.use_consumer_cwd:
            consumer_root = os.environ.get("PREVUE_CONSUMER_ROOT", "")
            if consumer_root and os.path.isdir(consumer_root):
                cwd = consumer_root

        # Prompt delivery
        if spec.prompt_delivery == "stdin":
            # Append model argv flag before invocation (model last for stdin engines)
            if spec.model_flag == "argv" and model and spec.model_argv_flag:
                cmd.extend([spec.model_argv_flag, model])
            return invoke_subprocess_text(
                cmd,
                env=env,
                secret=token,
                budget_seconds=budget_seconds,
                cli_label=spec.cli_label,
                input_text=prompt,
                cwd=cwd,
            )

        elif spec.prompt_delivery == "tempfile-arg":
            # Write prompt to a NamedTemporaryFile, pass via tempfile_flag ("-f")
            # Order: base_argv → tempfile_flag + path → model_argv_flag + model
            # (matches original cursor_cli.py:42-44 order; test_cursor_model_mapping asserts last 2)
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
            tmp_path = tmp.name
            try:
                tmp.write(prompt)
                tmp.close()
                if spec.tempfile_flag:
                    cmd.extend([spec.tempfile_flag, tmp_path])
                if spec.model_flag == "argv" and model and spec.model_argv_flag:
                    cmd.extend([spec.model_argv_flag, model])
                return invoke_subprocess_text(
                    cmd,
                    env=env,
                    secret=token,
                    budget_seconds=budget_seconds,
                    cli_label=spec.cli_label,
                    cwd=cwd,
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        else:  # prompt_delivery == "argv"
            # Model flag appended first, then prompt as the final element
            if spec.model_flag == "argv" and model and spec.model_argv_flag:
                cmd.extend([spec.model_argv_flag, model])
            cmd.append(prompt)
            return invoke_subprocess_text(
                cmd,
                env=env,
                secret=token,
                budget_seconds=budget_seconds,
                cli_label=spec.cli_label,
                cwd=cwd,
            )

    # ------------------------------------------------------------------
    # EngineAdapter interface
    # ------------------------------------------------------------------

    def review(self, req: ReviewRequest) -> ReviewResult:
        token, env = self._build_env(req.model)
        return flow.review_with_retry(
            req,
            invoke=lambda p: self._invoke(p, env, token, req.budget_seconds, req.model),
            secret=token,
            build_prompt=build_prompt,
            max_prompt_bytes=_prompt_module.MAX_PROMPT_BYTES,
            model_label=req.model or "default",
        )

    def classify(
        self,
        paths: list[str],
        allowed_labels: tuple[str, ...] | list[str],
        *,
        model: str | None = None,
    ) -> dict[str, str]:
        token, env = self._build_env(model)
        prompt = build_classify_prompt(paths, allowed_labels)
        text = self._invoke(prompt, env, token, CLASSIFY_TIMEOUT_SECONDS, model)
        return parse_classify_response(text, paths, allowed_labels)

    def classify_skills(
        self,
        skills: list,
        allowed_labels: tuple[str, ...] | list[str],
        *,
        model: str | None = None,
        paths: list[str] | None = None,
        diff_excerpt: str | None = None,
    ) -> dict[str, str]:
        token, env = self._build_env(model)
        names = [s.name for s in skills]
        prompt = build_skill_select_prompt(
            skills, allowed_labels, paths=paths, diff_excerpt=diff_excerpt
        )
        text = self._invoke(prompt, env, token, CLASSIFY_TIMEOUT_SECONDS, model)
        return parse_classify_response(text, names, allowed_labels)
