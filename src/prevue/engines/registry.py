"""Engine name → adapter registry with fail-closed selection (D-03/D-04)."""

from __future__ import annotations

from prevue.engines.base import EngineAdapter
from prevue.engines.claude_code_cli import ClaudeCodeAdapter
from prevue.engines.copilot_cli import CopilotCliAdapter
from prevue.engines.cursor_cli import CursorAdapter
from prevue.engines.gemini_cli import GeminiAdapter

DEFAULT_ENGINE = "copilot-cli"

ENGINES: dict[str, type[EngineAdapter]] = {
    CopilotCliAdapter.name: CopilotCliAdapter,
    ClaudeCodeAdapter.name: ClaudeCodeAdapter,
    CursorAdapter.name: CursorAdapter,
    GeminiAdapter.name: GeminiAdapter,
}


class UnknownEngineError(ValueError):
    """Raised when PREVUE_ENGINE names an unregistered adapter."""


def get_adapter(name: str) -> EngineAdapter:
    try:
        cls = ENGINES[name]
    except KeyError as e:
        valid = ", ".join(sorted(ENGINES))
        raise UnknownEngineError(f"Unknown PREVUE_ENGINE {name!r}; valid engines: {valid}") from e
    return cls()
