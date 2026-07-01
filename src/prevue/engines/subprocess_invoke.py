"""Shared subprocess invoke helpers for CLI engine adapters."""

from __future__ import annotations

import subprocess

from prevue.engines.errors import EngineFailure, sanitize_stderr


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
        stderr = sanitize_stderr(proc.stderr, secret)
        stdout = sanitize_stderr(proc.stdout, secret)
        raise EngineFailure(
            f"{cli_label} exited {proc.returncode}: stderr={stderr!r} stdout={stdout!r}"
        )

    review_text = proc.stdout.strip()
    if not review_text:
        raise EngineFailure(f"{cli_label} returned empty output")
    return review_text
