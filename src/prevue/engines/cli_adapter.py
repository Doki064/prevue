"""Generic CLI engine adapter driven by CliEngineSpec (ENGN-10, D-01).

One concrete adapter implements review/classify/classify_skills for ALL CLI engines.
Adding a CLI engine = one CliEngineSpec data entry in spec.py; no subclass needed.
"""

from __future__ import annotations

import os
import shlex
import tempfile
import uuid

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


def _build_copilot_otel_path(base_dir: str) -> str | None:
    """Fresh per-attempt Copilot OTEL leaf path under base_dir.

    The leaf .jsonl must not exist when Copilot starts (exporter no-ops otherwise).
    Each call gets base_dir/<uuid>/<uuid>.jsonl so directory globs cannot cross calls.
    """
    try:
        attempt_dir = os.path.join(base_dir, uuid.uuid4().hex)
        os.makedirs(attempt_dir, exist_ok=True)
    except OSError:
        return None
    return os.path.join(attempt_dir, f"{uuid.uuid4().hex}.jsonl")


class CliEngineAdapter(EngineAdapter):
    """Single generic CLI engine adapter parameterized by a CliEngineSpec.

    All CLI engines (copilot, claude-code, cursor, antigravity) share this implementation.
    Per-engine variation is captured declaratively in CliEngineSpec (spec.py).

    raw_args (ENGN-08/D-10): optional list of extra CLI flags appended LAST to every
    argv.  Set from EngineConfig.raw_args (parsed from the base-ref prevue.yml) by
    review.py after calling get_adapter().  Default [] means byte-identical behavior
    to the pre-Plan-04 code when no extra flags are configured.
    """

    def __init__(
        self,
        spec: CliEngineSpec,
        raw_args: list[str] | None = None,
        pricing_override: dict | None = None,
    ) -> None:
        self._spec = spec
        self.name = spec.name
        # raw_args appended LAST after all framework argv (ENGN-08/D-10: list form only)
        self._raw_args: list[str] = list(raw_args) if raw_args else []
        # pricing_override: consumer engine.pricing dict (D-06c); None = use vendored table
        self._pricing_override: dict | None = pricing_override

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_env(self, model: str | None) -> tuple[str, dict[str, str]]:
        """Validate secret, build subprocess env. Raises spec.auth_error on failure."""
        spec = self._spec
        raw_token = os.environ.get(spec.secret_env, "")
        if not raw_token:
            for alias in spec.secret_env_aliases:
                raw_token = os.environ.get(alias, "")
                if raw_token:
                    break
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

        # Q-06: shared invoke kwargs; each delivery branch only varies input/cmd/env.
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

        elif spec.prompt_delivery == "stdin-or-argv":
            # Under argv_prompt_max_bytes use -p (Copilot OTEL path); else stdin.
            _extend_model_argv(cmd, spec, model)
            prompt_bytes = len(prompt.encode("utf-8"))
            under_ceiling = (
                spec.argv_prompt_max_bytes is not None
                and prompt_bytes <= spec.argv_prompt_max_bytes
            )
            if under_ceiling:
                cmd.append("-p")
                cmd.append(prompt)
            if raw_args:
                cmd.extend(raw_args)
            if under_ceiling:
                return _do_invoke(cmd)
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

            # argv_pty_wrap: non-TTY CLIs (e.g. agy) need script -qec + ANSI strip.
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
        otel_path: str | None = None
        retry_otel_path: str | None = None
        base_otel_dir: str | None = None
        if self._spec.usage_capture == "otel-jsonl":
            base_otel_dir = os.environ.get("COPILOT_OTEL_FILE_EXPORTER_PATH")
            if base_otel_dir:
                otel_path = _build_copilot_otel_path(base_otel_dir)
                retry_otel_path = _build_copilot_otel_path(base_otel_dir)

        attempt_paths = [otel_path, retry_otel_path]
        raw_args = self._raw_args  # capture for lambda

        def _invoke_attempt(p: str) -> str:
            if attempt_paths:
                attempt_path = attempt_paths.pop(0)
            elif base_otel_dir:
                # Beyond the first two invocations (e.g. a future added retry):
                # mint a fresh path rather than reusing retry_otel_path, which a
                # prior call already wrote — Copilot's OTEL exporter silently
                # no-ops on an existing path, which would corrupt that call's
                # token accounting (phase-10 review).
                attempt_path = _build_copilot_otel_path(base_otel_dir)
            else:
                attempt_path = None
            attempt_env = env
            if attempt_path is not None:
                attempt_env = {**env, "COPILOT_OTEL_FILE_EXPORTER_PATH": attempt_path}
            return self._invoke(
                p, attempt_env, token, req.budget_seconds, req.model, raw_args=raw_args
            )

        return flow.review_with_retry(
            req,
            invoke=_invoke_attempt,
            secret=token,
            build_prompt=build_prompt,
            max_prompt_bytes=_prompt_module.MAX_PROMPT_BYTES,
            model_label=req.model or "default",
            spec=self._spec,
            pricing_override=self._pricing_override,
            otel_path=otel_path,
            retry_otel_path=retry_otel_path,
        )

    def _unwrap_classify_text(self, raw_stdout: str) -> str:
        """Unwrap json_envelope stdout so classify parsers see the inner JSON."""
        from prevue.engines.usage import unwrap_envelope_result

        return unwrap_envelope_result(self._spec, raw_stdout)

    def classify(
        self,
        paths: list[str],
        allowed_labels: tuple[str, ...] | list[str],
        *,
        model: str | None = None,
    ) -> dict[str, str]:
        labels, _ = self.classify_with_tokens(paths, allowed_labels, model=model)
        return labels

    def classify_with_tokens(
        self,
        paths: list[str],
        allowed_labels: tuple[str, ...] | list[str],
        *,
        model: str | None = None,
    ) -> tuple[dict[str, str], int | None]:
        """Classify paths and return (labels, real_token_count).

        real_token_count is input+output tokens from the engine's JSON envelope
        (json_envelope specs only). None for plain-stdout engines.
        """
        token, env = self._build_env(model)
        prompt = build_classify_prompt(paths, allowed_labels)
        # raw_args not passed to classify — extra engine flags are review-only (D-10)
        raw = self._invoke(prompt, env, token, CLASSIFY_TIMEOUT_SECONDS, model)
        labels = parse_classify_response(self._unwrap_classify_text(raw), paths, allowed_labels)
        real_tokens: int | None = None
        if self._spec.stdout_format == "json_envelope":
            from prevue.engines.usage import parse_envelope

            envelope = parse_envelope(raw)
            if envelope is not None:
                usage = envelope.get("usage")
                if isinstance(usage, dict):
                    inp = usage.get("input_tokens") or 0
                    out = usage.get("output_tokens") or 0
                    real_tokens = int(inp) + int(out)
        return labels, real_tokens

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
        raw = self._invoke(prompt, env, token, CLASSIFY_TIMEOUT_SECONDS, model)
        return parse_classify_response(self._unwrap_classify_text(raw), names, allowed_labels)
