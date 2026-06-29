"""Shared engine adapter errors and stderr sanitization."""

from __future__ import annotations


class AuthError(RuntimeError):
    """Raised when a required engine credential is missing or malformed (pre-subprocess)."""


class EngineFailure(RuntimeError):
    """Raised when an engine CLI fails, times out, or returns unusable output."""


def sanitize_stderr(stderr: str | bytes | None, secret: str) -> str:
    """Truncate stderr and redact the auth secret so it never appears in errors."""
    try:
        if isinstance(stderr, bytes):
            snippet = stderr.decode("utf-8", errors="replace")[-500:]
        else:
            snippet = (stderr or "")[-500:]
    except (UnicodeDecodeError, TypeError, AttributeError):
        snippet = "<stderr decode failed>"
    if secret:
        snippet = snippet.replace(secret, "[REDACTED]")
    return snippet


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
