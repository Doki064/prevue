"""Shared subprocess invoke helpers for CLI engine adapters."""

from __future__ import annotations

import re
import subprocess

from prevue.engines.errors import EngineFailure, sanitize_stderr

# Matches env var names that plausibly hold a credential (TOKEN/KEY/SECRET/PASSWORD),
# so any of them appearing verbatim in captured stdout/stderr gets redacted too —
# not just the one secret this particular engine invocation was built around.
_SECRET_ENV_NAME = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD)", re.IGNORECASE)


_MIN_SECRET_LEN = 12  # below this, a short common substring risks mass-redacting unrelated text


def _env_secrets(env: dict[str, str]) -> list[str]:
    return [
        value
        for key, value in env.items()
        if value and len(value) >= _MIN_SECRET_LEN and _SECRET_ENV_NAME.search(key)
    ]


def invoke_subprocess_text(
    cmd: list[str],
    *,
    env: dict[str, str],
    secret: str,
    budget_seconds: int,
    cli_label: str,
    input_text: str | None = None,
    cwd: str | None = None,
) -> str:
    """Run a headless CLI, return trimmed stdout, or raise EngineFailure."""
    try:
        proc = subprocess.run(
            cmd,
            input=input_text,
            env=env,
            capture_output=True,
            text=True,
            timeout=budget_seconds,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        raise EngineFailure(f"{cli_label} timed out after {budget_seconds}s") from exc

    if proc.returncode != 0:
        extra_secrets = _env_secrets(env)
        stderr = sanitize_stderr(proc.stderr, secret, extra_secrets)
        stdout = sanitize_stderr(proc.stdout, secret, extra_secrets)
        raise EngineFailure(
            f"{cli_label} exited {proc.returncode}: stderr={stderr!r} stdout={stdout!r}"
        )

    review_text = proc.stdout.strip()
    if not review_text:
        raise EngineFailure(f"{cli_label} returned empty output")
    return review_text
