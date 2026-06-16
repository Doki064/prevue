"""Shared retry-then-degrade review flow for all engine adapters (D-08)."""

from __future__ import annotations

import time
from collections.abc import Callable

from prevue.engines.errors import EngineFailure
from prevue.engines.parsing import extract_json_fence, validate_findings
from prevue.engines.prompt import _build_retry_prompt
from prevue.engines.tokens import estimate_tokens
from prevue.models import ReviewRequest, ReviewResult


def _token_meta(prompt: str, stdout: str = "") -> dict[str, int | bool]:
    return {
        "review": estimate_tokens(prompt) + estimate_tokens(stdout),
        "estimated": True,
    }


def _retry_token_meta(
    prompt: str, retry_prompt: str, first_stdout: str, retry_stdout: str
) -> dict[str, int | bool]:
    """Sum both invocations' real inputs/outputs once each.

    `retry_prompt` already embeds the full original `prompt` (see _build_retry_prompt),
    so it is counted as the second invocation's input on its own — never concatenated
    onto `prompt`, which would count the original prompt twice.
    """
    return {
        "review": (
            estimate_tokens(prompt)
            + estimate_tokens(first_stdout)
            + estimate_tokens(retry_prompt)
            + estimate_tokens(retry_stdout)
        ),
        "estimated": True,
    }


def _degraded_result(
    prose: str,
    parse_error: str,
    req: ReviewRequest,
    start: float,
    *,
    retried: bool,
    dropped_findings: int = 0,
    model_label: str,
    tokens: dict[str, int | bool],
) -> ReviewResult:
    meta: dict[str, object] = {
        "model": model_label,
        "duration_s": round(time.monotonic() - start, 1),
        "retried": retried,
        "parse_error": parse_error,
        "tokens": tokens,
    }
    return ReviewResult(
        summary_markdown=prose,
        findings=[],
        degraded=True,
        dropped_findings=dropped_findings,
        engine_meta=meta,
    )


def review_with_retry(
    req: ReviewRequest,
    *,
    invoke: Callable[[str], str],
    secret: str,
    build_prompt: Callable[..., str],
    max_prompt_bytes: int,
    model_label: str,
) -> ReviewResult:
    prompt = build_prompt(
        req,
        known_issues=req.known_issues,
        max_known_issues=req.max_known_issues,
    )
    prompt_bytes = len(prompt.encode("utf-8"))
    if prompt_bytes > max_prompt_bytes:
        raise EngineFailure(
            f"Prompt exceeds 1MB ({prompt_bytes:,} bytes); use file-based fallback in Phase 6"
        )

    start = time.monotonic()
    retried = False
    retry_prompt = ""

    stdout = invoke(prompt)
    first_stdout = stdout
    prose, payload, fence_err = extract_json_fence(stdout)

    if fence_err:
        retry_prompt = _build_retry_prompt(prompt, fence_err)
        if len(retry_prompt.encode("utf-8")) > max_prompt_bytes:
            return _degraded_result(
                prose,
                fence_err,
                req,
                start,
                retried=False,
                model_label=model_label,
                tokens=_token_meta(prompt, first_stdout),
            )

        retried = True
        try:
            stdout = invoke(retry_prompt)
        except EngineFailure:
            # Retry input was sent but produced no output before failing.
            return _degraded_result(
                prose,
                fence_err,
                req,
                start,
                retried=True,
                model_label=model_label,
                tokens=_retry_token_meta(prompt, retry_prompt, first_stdout, ""),
            )

        prose, payload, fence_err = extract_json_fence(stdout)
        if fence_err:
            return _degraded_result(
                prose,
                fence_err,
                req,
                start,
                retried=True,
                model_label=model_label,
                tokens=_retry_token_meta(prompt, retry_prompt, first_stdout, stdout),
            )

    def _tokens() -> dict[str, int | bool]:
        if retried:
            return _retry_token_meta(prompt, retry_prompt, first_stdout, stdout)
        return _token_meta(prompt, stdout)

    valid, dropped = validate_findings(payload or [])
    if payload and not valid:
        return ReviewResult(
            summary_markdown=prose,
            findings=[],
            degraded=True,
            dropped_findings=len(payload),
            engine_meta={
                "model": model_label,
                "duration_s": round(time.monotonic() - start, 1),
                "retried": retried,
                "tokens": _tokens(),
            },
        )

    return ReviewResult(
        summary_markdown=prose,
        findings=valid,
        degraded=False,
        dropped_findings=dropped,
        engine_meta={
            "model": model_label,
            "duration_s": round(time.monotonic() - start, 1),
            "retried": retried,
            "tokens": _tokens(),
        },
    )
