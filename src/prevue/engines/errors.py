"""Shared engine adapter errors and stderr sanitization."""

from __future__ import annotations

from collections.abc import Iterable


class AuthError(RuntimeError):
    """Raised when a required engine credential is missing or malformed (pre-subprocess)."""


class EngineFailure(RuntimeError):
    """Raised when an engine CLI fails, times out, or returns unusable output."""


def sanitize_stderr(
    stderr: str | bytes | None,
    secret: str,
    extra_secrets: Iterable[str] = (),
) -> str:
    """Redact the auth secret (plus any extra_secrets) then truncate.

    extra_secrets covers other credentials present in the subprocess env (e.g.
    a sibling engine's token) that could otherwise leak unredacted into stdout
    included in EngineFailure messages.
    """
    try:
        if isinstance(stderr, bytes):
            full = stderr.decode("utf-8", errors="replace")
        else:
            full = stderr or ""
    except (UnicodeDecodeError, TypeError, AttributeError):
        return "<stderr decode failed>"
    for value in (secret, *extra_secrets):
        if value:
            full = full.replace(value, "[REDACTED]")
    return full[-500:]


_sanitize_stderr = sanitize_stderr


# ---------------------------------------------------------------------------
# Per-engine AuthError subclasses — defined here to avoid circular imports
# (spec.py imports these; per-engine modules re-export for test compat)
# ---------------------------------------------------------------------------


class CopilotAuthError(AuthError):
    """Raised when COPILOT_GITHUB_TOKEN is missing or not a fine-grained PAT."""


class ClaudeAuthError(AuthError):
    """Raised when CLAUDE_CODE_OAUTH_TOKEN is missing."""


class CursorAuthError(AuthError):
    """Raised when CURSOR_API_KEY is missing."""


class AntigravityAuthError(AuthError):
    """Raised when ANTIGRAVITY_API_KEY is missing."""
