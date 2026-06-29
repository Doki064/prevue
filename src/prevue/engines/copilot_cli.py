"""Copilot CLI auth error + re-exports preserved for test/import compatibility (ENGN-10).

The full adapter is now CliEngineAdapter(spec) in cli_adapter.py, driven by
the copilot-cli CliEngineSpec in spec.py. This module retains:
  - CopilotAuthError (tests assert on this type via prevue.engines.errors)
  - CopilotCliAdapter backward-compat alias
  - __all__ re-exports that tests import directly (Pitfall 5)
  - _sanitize_stderr alias (test_copilot_adapter.py imports it)
"""

from __future__ import annotations

from prevue.engines.errors import (  # noqa: F401 — re-export for backward compat
    CopilotAuthError,
    EngineFailure,
    sanitize_stderr,
)
from prevue.engines.prompt import (  # noqa: F401 — re-export for backward compat
    MAX_PROMPT_BYTES,
    OUTPUT_CONTRACT,
    _build_prompt,
    _build_retry_prompt,
    _escape_line,
    _safe_diff_block,
    build_prompt,
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

_sanitize_stderr = sanitize_stderr


# Backward-compat alias — test_registry.py imports CopilotCliAdapter and checks isinstance().
# The real adapter is CliEngineAdapter; this alias wraps it for the copilot-cli spec.
from prevue.engines.cli_adapter import CliEngineAdapter as _CliEngineAdapter  # noqa: E402
from prevue.engines.spec import CLI_ENGINE_SPECS  # noqa: E402


def _get_copilot_spec():
    return next(s for s in CLI_ENGINE_SPECS if s.name == "copilot-cli")


class CopilotCliAdapter(_CliEngineAdapter):
    """Backward-compatible alias: CliEngineAdapter configured for copilot-cli."""

    def __init__(self) -> None:
        super().__init__(_get_copilot_spec())
