"""Engine name → adapter registry with fail-closed selection (D-03/D-04)."""

from __future__ import annotations

from prevue.engines.base import EngineAdapter
from prevue.engines.claude_code_cli import ClaudeCodeAdapter
from prevue.engines.copilot_cli import CopilotCliAdapter
from prevue.engines.cursor_cli import CursorAdapter
from prevue.engines.gemini_cli import GeminiAdapter

DEFAULT_ENGINE = "copilot-cli"
SKELETON_ENGINES = frozenset({GeminiAdapter.name})

ENGINES: dict[str, type[EngineAdapter]] = {
    CopilotCliAdapter.name: CopilotCliAdapter,
    ClaudeCodeAdapter.name: ClaudeCodeAdapter,
    CursorAdapter.name: CursorAdapter,
    GeminiAdapter.name: GeminiAdapter,
}

FUNCTIONAL_ENGINES = frozenset(name for name in ENGINES if name not in SKELETON_ENGINES)


class UnknownEngineError(ValueError):
    """Raised when PREVUE_ENGINE names an unregistered adapter."""


class NonFunctionalEngineError(ValueError):
    """Raised when a registered skeleton engine is selected for review."""


def get_adapter(name: str) -> EngineAdapter:
    try:
        cls = ENGINES[name]
    except KeyError as e:
        valid = ", ".join(sorted(ENGINES))
        raise UnknownEngineError(f"Unknown PREVUE_ENGINE {name!r}; valid engines: {valid}") from e
    return cls()


def require_functional_adapter(name: str) -> EngineAdapter:
    """Resolve an adapter that can run reviews (excludes skeleton engines)."""
    if name in SKELETON_ENGINES:
        raise NonFunctionalEngineError(
            f"Engine {name!r} is registered but not yet functional; "
            f"choose one of: {', '.join(sorted(FUNCTIONAL_ENGINES))}"
        )
    return get_adapter(name)
