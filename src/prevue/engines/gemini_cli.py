"""Antigravity CLI auth error — replaces Gemini skeleton (D-12, ENGN-10).

D-12: Gemini CLI replaced by Antigravity CLI (`agy` binary).
The full adapter is implemented via CliEngineAdapter(spec) in cli_adapter.py.
This module exists for import stability and AuthError test compatibility.

Risk note: Antigravity's non-TTY stdout-dropping behavior and unstable
--output-format json (RESEARCH §10-RESEARCH Open Q2) mean token reporting
cannot be confirmed without a live CI test. Plan 06 handles install plumbing.
"""

from __future__ import annotations

from prevue.engines.errors import AuthError


class AntigravityAuthError(AuthError):
    """Raised when ANTIGRAVITY_API_KEY is missing."""
