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
