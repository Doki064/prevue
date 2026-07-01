"""Generic CLI engine adapter driven by CliEngineSpec (ENGN-10, D-01).

One concrete adapter implements review/classify/classify_skills for ALL CLI engines.
Adding a CLI engine = one CliEngineSpec data entry in spec.py; no subclass needed.
"""

from __future__ import annotations

import os
import shlex
import tempfile

import prevue.engines.prompt as _prompt_module
from prevue.engines import flow
from prevue.engines.base import EngineAdapter
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


def _extend_model_argv(cmd: list[str], spec: CliEngineSpec, model: str | None) -> None:
    """Append model argv flag+value to cmd in-place — no-op when model not set (Q-06)."""
    if spec.model_flag == "argv" and model and spec.model_argv_flag:
        cmd.extend([spec.model_argv_flag, model])


class CliEngineAdapter(EngineAdapter):
    """Single generic CLI engine adapter parameterized by a CliEngineSpec.

    All CLI engines (copilot, claude-code, cursor, antigravity) share this implementation.
    Per-engine variation is captured declaratively in CliEngineSpec (spec.py).

    raw_args (ENGN-08/D-10): optional list of extra CLI flags appended LAST to every
    argv.  Set from EngineConfig.raw_args (parsed from the base-ref prevue.yml) by
    review.py after calling get_adapter().  Default [] means byte-identical behavior
    to the pre-Plan-04 code when no extra flags are configured.
    """

    def __init__(self, spec: CliEngineSpec, raw_args: list[str] | None = None) -> None:
        self._spec = spec
        self.name = spec.name
        # raw_args appended LAST after all framework argv (ENGN-08/D-10: list form only)
        self._raw_args: list[str] = list(raw_args) if raw_args else []
        # pricing_override: consumer engine.pricing dict (D-06c); None = use vendored table
        self._pricing_override: dict | None = None

    def set_raw_args(self, raw_args: list[str]) -> None:
        """Replace the raw_args list (ENGN-08/D-10: called from review.py after get_adapter)."""
        self._raw_args = list(raw_args)

    def set_pricing_override(self, pricing: dict | None) -> None:
        """Set the consumer pricing override dict (D-06c: called from review.py after
        load_config)."""
        self._pricing_override = pricing

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_env(self, model: str | None) -> tuple[str, dict[str, str]]:
        """Validate secret, build subprocess env. Raises spec.auth_error on failure."""
        spec = self._spec
        raw_token = os.environ.get(spec.secret_env, "")
        # D-12: GEMINI_API_KEY is accepted as an alias for ANTIGRAVITY_API_KEY
        if not raw_token and spec.name == "antigravity-cli":
            raw_token = os.environ.get("GEMINI_API_KEY", "")
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
        raw_args: list[str] | None = None,
    ) -> str:
        """Assemble argv + invoke subprocess per spec configuration.

        argv order (ENGN-08/D-10):
          base_argv + prompt-delivery flags + model flag + raw_args (LAST, list form)

        raw_args are appended after all framework-generated argv elements.
        Never shell-joined; always list form; no shell=True (D-10: command injection guard).
        """
        spec = self._spec
        cmd = list(spec.base_argv)

        # Determine cwd for cursor-style adapters
        cwd: str | None = None
        if spec.use_consumer_cwd:
            consumer_root = os.environ.get("PREVUE_CONSUMER_ROOT", "")
            if consumer_root and os.path.isdir(consumer_root):
                cwd = consumer_root

        # Q-06 (10-THERMOS): local closure captures shared invoke kwargs so each
        # delivery branch only spells out the variation (input_text, cmd, env).
        def _do_invoke(c: list[str], input_text: str | None = None, e: dict | None = None) -> str:
            return invoke_subprocess_text(
                c,
                env=e if e is not None else env,
                secret=token,
                budget_seconds=budget_seconds,
                cli_label=spec.cli_label,
                input_text=input_text,
                cwd=cwd,
            )

        # Prompt delivery
        if spec.prompt_delivery == "stdin":
            # base_argv → model_argv → raw_args; prompt on stdin
            _extend_model_argv(cmd, spec, model)
            if raw_args:
                cmd.extend(raw_args)
            return _do_invoke(cmd, input_text=prompt)

        elif spec.prompt_delivery == "tempfile-arg":
            # base_argv → tempfile_flag + path → model_argv → raw_args
            # Order asserted by test_cursor_model_mapping (last 2 in cmd are -m <model>)
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
            tmp_path = tmp.name
            try:
                tmp.write(prompt)
                tmp.close()
                if spec.tempfile_flag:
                    cmd.extend([spec.tempfile_flag, tmp_path])
                _extend_model_argv(cmd, spec, model)
                if raw_args:
                    cmd.extend(raw_args)
                return _do_invoke(cmd)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        else:  # prompt_delivery == "argv"
            # base_argv → model_argv → prompt (last) → raw_args
            _extend_model_argv(cmd, spec, model)
            cmd.append(prompt)
            if raw_args:
                cmd.extend(raw_args)

            # Pitfall 2 (D-12 / T-10-21): some argv CLIs (e.g. agy) check isatty at
            # startup and silently drop output when running under GitHub Actions (non-TTY).
            # Wrap via `script -qec` to provide a pseudo-TTY, then strip ANSI + CR.
            # Controlled by spec.argv_pty_wrap (Q-04, 10-THERMOS).
            #
            # Implementation: store prompt in env var _AGY_PROMPT and build the inner
            # shell command string using $var substitution — no shell-quoting of prompt
            # needed, so the wrapper is safe regardless of prompt content.
            # $_AGY_PROMPT must be double-quoted so the shell expands it as a single
            # arg regardless of spaces/globs. shlex.quote would single-quote it, which
            # suppresses expansion. (shlex.quote-safe parts use shlex.quote; prompt only
            # via env var, never shell-spliced.)
            #
            # Static assertion target: grep -Rq "script -qec" src/prevue/engines/
            if spec.argv_pty_wrap:
                pty_cmd = list(spec.base_argv)
                _extend_model_argv(pty_cmd, spec, model)
                if raw_args:
                    pty_cmd.extend(raw_args)
                inner_cmd = " ".join(shlex.quote(p) for p in pty_cmd) + ' "$_AGY_PROMPT"'
                wrapper_cmd = (
                    f"script -qec {shlex.quote(inner_cmd)} /dev/null"
                    " | sed -r 's/\\x1B\\[[0-9;]*[A-Za-z]//g' | tr -d '\\r'"
                )
                return _do_invoke(["bash", "-c", wrapper_cmd], e={**env, "_AGY_PROMPT": prompt})

            return _do_invoke(cmd)

    # ------------------------------------------------------------------
    # EngineAdapter interface
    # ------------------------------------------------------------------

    def review(self, req: ReviewRequest) -> ReviewResult:
        token, env = self._build_env(req.model)
        # Pass spec so flow can capture real per-engine usage (PERF-03, D-04).
        # For otel-jsonl engines (copilot-cli), flow reads COPILOT_OTEL_FILE_EXPORTER_PATH
        # from the environment post-invocation (WARNING 3: env is unset until Plan 05
        # wires it into the workflow — Copilot falls back to bytes/4 until then).
        raw_args = self._raw_args  # capture for lambda
        return flow.review_with_retry(
            req,
            invoke=lambda p: self._invoke(
                p, env, token, req.budget_seconds, req.model, raw_args=raw_args
            ),
            secret=token,
            build_prompt=build_prompt,
            max_prompt_bytes=_prompt_module.MAX_PROMPT_BYTES,
            model_label=req.model or "default",
            spec=self._spec,
            pricing_override=self._pricing_override,
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
        # raw_args not passed to classify — extra engine flags are review-only (D-10)
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
        # raw_args not passed to classify_skills — extra engine flags are review-only (D-10)
        text = self._invoke(prompt, env, token, CLASSIFY_TIMEOUT_SECONDS, model)
        return parse_classify_response(text, names, allowed_labels)
