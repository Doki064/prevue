"""Declarative engine specifications + CLI_ENGINE_SPECS registry list (ENGN-10, D-01/D-03)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

# AuthError subclasses are imported from their per-engine modules for test compat.
# These imports happen at module load after those modules define the error classes.
from prevue.engines.claude_code_cli import ClaudeAuthError
from prevue.engines.copilot_cli import CopilotAuthError
from prevue.engines.cursor_cli import CursorAuthError
from prevue.engines.gemini_cli import AntigravityAuthError


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
        usage_capture="otel-jsonl",
        functional=True,
    ),
    CliEngineSpec(
        name="claude-code-cli",
        cli_label="Claude Code CLI",
        secret_env="ANTHROPIC_API_KEY",
        auth_error=ClaudeAuthError,
        validate_secret=_validate_nonempty_secret(ClaudeAuthError, "ANTHROPIC_API_KEY"),
        base_argv=("claude", "--bare", "-p", "--output-format", "text"),
        prompt_delivery="stdin",
        model_flag="argv",
        model_argv_flag="--model",
        usage_capture="stdout-json",
        functional=True,
    ),
    CliEngineSpec(
        name="cursor-cli",
        cli_label="Cursor CLI",
        secret_env="CURSOR_API_KEY",
        auth_error=CursorAuthError,
        validate_secret=_validate_nonempty_secret(CursorAuthError, "CURSOR_API_KEY"),
        base_argv=("cursor-agent", "-p", "--output-format", "text"),
        prompt_delivery="tempfile-arg",
        tempfile_flag="-f",
        model_flag="argv",
        model_argv_flag="-m",
        use_consumer_cwd=True,
        usage_capture="none",
        functional=True,
    ),
    CliEngineSpec(
        name="antigravity-cli",
        cli_label="Antigravity CLI",
        # D-12: GEMINI_API_KEY is accepted as an alias; primary var is ANTIGRAVITY_API_KEY.
        # validate_secret checks ANTIGRAVITY_API_KEY env; consumer may also set GEMINI_API_KEY
        # as a documented alias (see registry.py — registry keys on the spec name, not env alias).
        secret_env="ANTIGRAVITY_API_KEY",
        auth_error=AntigravityAuthError,
        validate_secret=_validate_nonempty_secret(AntigravityAuthError, "ANTIGRAVITY_API_KEY"),
        base_argv=("agy", "-p"),
        prompt_delivery="argv",
        model_flag="argv",
        model_argv_flag="--model",
        usage_capture="none",
        functional=True,
    ),
)
