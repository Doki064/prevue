"""Declarative engine specifications + CLI_ENGINE_SPECS registry list (ENGN-10, D-01/D-03)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

# AuthError subclasses are defined in errors.py to avoid circular imports.
# Per-engine modules re-export them for test backward compat.
from prevue.engines.errors import (
    AntigravityAuthError,
    AuthError,  # noqa: F401 — re-exported for convenience
    ClaudeAuthError,
    CopilotAuthError,
    CursorAuthError,
)


class CliEngineSpec(BaseModel):
    """Frozen, declarative spec for a CLI-backed engine adapter (D-01).

    Adding a CLI engine = one CliEngineSpec entry in CLI_ENGINE_SPECS.
    No subclass, no duplicated adapter methods.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    # Identity
    name: str
    cli_label: str

    # Auth
    secret_env: str
    auth_error: type  # CopilotAuthError | ClaudeAuthError | ...  (test compat — Pitfall 5)
    validate_secret: Callable[[str], str]  # returns secret or raises auth_error
    # secret_env_aliases (T-10 / D-12, 10-THERMOS quick task): env vars checked, in
    # order, when secret_env is unset — e.g. antigravity-cli accepts GEMINI_API_KEY
    # as a documented alias for ANTIGRAVITY_API_KEY. Declarative spec data replaces
    # the `spec.name == "antigravity-cli"` name-check that previously lived in
    # cli_adapter._build_env (same anti-pattern argv_pty_wrap/D-01 avoid elsewhere).
    secret_env_aliases: tuple[str, ...] = ()

    # Subprocess argv
    base_argv: tuple[str, ...]

    # Prompt delivery: stdin | tempfile-arg | argv (prompt appended after -p)
    prompt_delivery: Literal["stdin", "tempfile-arg", "argv"]
    tempfile_flag: str | None = None  # "-f" for cursor-agent

    # Model flag: env (copilot sets COPILOT_MODEL) | argv (--model/-m flag) | none
    model_flag: Literal["env", "argv", "none"] = "none"
    model_env: str | None = None  # "COPILOT_MODEL"
    model_argv_flag: str | None = None  # "--model" | "-m"

    # Behaviour flags
    use_consumer_cwd: bool = False  # cursor: use PREVUE_CONSUMER_ROOT as cwd

    # Usage capture strategy (PERF-03, consumed in Plan 03)
    usage_capture: Literal["stdout-json", "otel-jsonl", "none"] = "none"

    # Stdout envelope format — separate axis from usage_capture (Q-03, 10-THERMOS).
    # "json_envelope": stdout is a JSON envelope; _resolve_fence_source unwraps the
    #   "result" field before running extract_json_fence (Pitfall 3 / D-01).
    # "plain": stdout is plain text; fence extraction runs on raw stdout.
    # Cursor uses "json_envelope" for its output format even though usage_capture="none"
    # (the envelope has no usage fields). Decoupled so the two axes evolve independently.
    stdout_format: Literal["plain", "json_envelope"] = "plain"

    # argv_pty_wrap: wrap argv-delivery invocation in a `script -qec` pseudo-TTY
    # (Q-04, 10-THERMOS). Extracted from the `if spec.name == "antigravity-cli"`
    # name-check in cli_adapter._invoke so the hack is a declarative spec flag
    # rather than a hard-coded engine name. Only meaningful when prompt_delivery="argv".
    # See Pitfall 2 (D-12 / T-10-21): agy checks isatty and silently drops output.
    argv_pty_wrap: bool = False

    # Functional flag — False means skeleton/not-yet-implemented (D-03)
    functional: bool = True


# ---------------------------------------------------------------------------
# Per-engine validate_secret helpers
# ---------------------------------------------------------------------------


def _validate_copilot_secret(token: str) -> str:
    """Validate COPILOT_GITHUB_TOKEN is a fine-grained PAT."""
    if not token.startswith("github_pat_"):
        raise CopilotAuthError(
            "COPILOT_GITHUB_TOKEN must be a fine-grained, user-owned PAT "
            "(github_pat_…) with the Copilot Requests permission."
        )
    return token


def _validate_nonempty_secret(error_class: type, env_var: str) -> Callable[[str], str]:
    """Return a validator that raises error_class when token is empty."""

    def _validate(token: str) -> str:
        if not token:
            raise error_class(f"{env_var} is not set.")
        return token

    return _validate


# ---------------------------------------------------------------------------
# CLI_ENGINE_SPECS — the authoritative list of all CLI engine specs
# ---------------------------------------------------------------------------

CLI_ENGINE_SPECS: tuple[CliEngineSpec, ...] = (
    # Gap 1 (10-08 gap closure, T-10-08 usage_capture): live sandbox verification (10-UAT.md)
    # confirmed COPILOT_OTEL_FILE_EXPORTER_PATH has no effect on the pinned
    # @github/copilot@1.0.61 CLI — `copilot --help` has zero OTEL/telemetry mention,
    # ~/.copilot is never created, and the exporter directory never appears. Checked
    # against official GitHub Copilot CLI docs and the github/copilot-cli repo (including
    # open issues): no OTEL export mechanism ships on this CLI today — an open feature
    # request ("Enterprise OTel auth ... parity with Claude Code") confirms this is
    # requested-but-unshipped, not a Prevue-side documentation gap (supersedes the stale
    # ccusage.com/guide/copilot secondary-source citation from 10-RESEARCH.md). Falls back
    # to the honest bytes/4 ~est estimate path (same as cursor-cli/antigravity-cli) instead
    # of falsely implying real-token capture via a non-functional wire. May be flipped back
    # to "otel-jsonl" if/when GitHub ships real OTEL export — usage.py's _parse_copilot_otel
    # parser and flow.py's otel-jsonl dispatch path are left unchanged (still correct, just
    # unreached for Copilot going forward).
    CliEngineSpec(
        name="copilot-cli",
        cli_label="Copilot CLI",
        secret_env="COPILOT_GITHUB_TOKEN",
        auth_error=CopilotAuthError,
        validate_secret=_validate_copilot_secret,
        base_argv=("copilot", "-s", "--no-ask-user"),
        prompt_delivery="stdin",
        model_flag="env",
        model_env="COPILOT_MODEL",
        usage_capture="none",
        functional=True,
    ),
    CliEngineSpec(
        name="claude-code-cli",
        cli_label="Claude Code CLI",
        # CLAUDE_CODE_OAUTH_TOKEN: long-lived token from `claude setup-token`, for CI pipelines.
        # --bare mode blocks CLAUDE_CODE_OAUTH_TOKEN (OAuth/keychain never read in --bare),
        # so we omit --bare here (T-08 / 10-THERMOS — see SECURITY.md for the tradeoff:
        # tried --safe-mode as a "fast + OAuth-compatible" middle ground, but measured
        # CI run showed the 283s/300s budget usage was real Claude generation time on a
        # large diff, not --bare-vs-unflagged startup overhead — so budget was raised
        # instead; --safe-mode added no measurable benefit and was reverted).
        # Subscription users (Pro/Max/Team/Enterprise) use this path; ANTHROPIC_API_KEY
        # is Console-only (pay-per-use API) and belongs to the future direct-API engine.
        secret_env="CLAUDE_CODE_OAUTH_TOKEN",
        auth_error=ClaudeAuthError,
        validate_secret=_validate_nonempty_secret(ClaudeAuthError, "CLAUDE_CODE_OAUTH_TOKEN"),
        base_argv=("claude", "-p", "--output-format", "json"),
        prompt_delivery="stdin",
        model_flag="argv",
        model_argv_flag="--model",
        usage_capture="stdout-json",
        stdout_format="json_envelope",
        functional=True,
    ),
    # Gap A (10-07 gap closure, T-10-07-G): official Cursor CLI docs
    # (cursor.com/docs/cli/reference/output-format) confirm the --output-format
    # json envelope schema is {type, subtype, is_error, duration_ms,
    # duration_api_ms, result, session_id, request_id} — no token/usage/cost
    # fields exist. Q-03 (10-THERMOS): stdout_format="json_envelope" decouples
    # the fence-unwrap need from usage_capture — Cursor produces a JSON envelope
    # but has no capturable token usage, so usage_capture="none" is now correct.
    CliEngineSpec(
        name="cursor-cli",
        cli_label="Cursor CLI",
        secret_env="CURSOR_API_KEY",
        auth_error=CursorAuthError,
        validate_secret=_validate_nonempty_secret(CursorAuthError, "CURSOR_API_KEY"),
        base_argv=("cursor-agent", "-p", "--output-format", "json"),
        prompt_delivery="tempfile-arg",
        tempfile_flag="-f",
        model_flag="argv",
        model_argv_flag="-m",
        use_consumer_cwd=True,
        usage_capture="none",
        stdout_format="json_envelope",
        functional=True,
    ),
    # Gap B (10-07 gap closure): official Antigravity CLI docs
    # (antigravity.google/docs/cli/install) confirm no API-key / non-interactive
    # auth mode exists for `agy`. The engine stays registered (get_adapter still
    # resolves it for future use if Antigravity ships headless auth) but
    # require_functional_adapter must reject it — closes the UAT gap where
    # functional=True shipped on an unconfirmed checkpoint that was never
    # closed (10-06-PLAN.md Task 3).
    CliEngineSpec(
        name="antigravity-cli",
        cli_label="Antigravity CLI",
        secret_env="ANTIGRAVITY_API_KEY",
        # D-12: GEMINI_API_KEY is accepted as an alias; primary var is ANTIGRAVITY_API_KEY.
        # validate_secret checks ANTIGRAVITY_API_KEY env; consumer may also set GEMINI_API_KEY
        # as a documented alias. Declarative spec data (T-10, 10-THERMOS quick task) — no
        # `spec.name ==` name-check in cli_adapter._build_env.
        secret_env_aliases=("GEMINI_API_KEY",),
        auth_error=AntigravityAuthError,
        validate_secret=_validate_nonempty_secret(AntigravityAuthError, "ANTIGRAVITY_API_KEY"),
        base_argv=("agy", "-p"),
        prompt_delivery="argv",
        model_flag="argv",
        model_argv_flag="--model",
        usage_capture="none",
        argv_pty_wrap=True,  # Q-04: agy checks isatty; wrap in script -qec pseudo-TTY
        functional=False,
    ),
)
