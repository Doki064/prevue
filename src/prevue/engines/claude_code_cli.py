"""Claude Code CLI auth error — preserved for import/test compatibility (ENGN-10).

The full adapter is now CliEngineAdapter(spec) in cli_adapter.py, driven by
the claude-code-cli CliEngineSpec in spec.py.
"""

from __future__ import annotations

from prevue.engines.errors import ClaudeAuthError  # noqa: F401 — re-export for test compat

__all__ = ["ClaudeAuthError"]
