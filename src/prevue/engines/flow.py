"""Shared retry-then-degrade review flow for all engine adapters (D-08)."""

from __future__ import annotations

import time
from collections.abc import Callable

from prevue.engines.errors import EngineFailure
from prevue.engines.parsing import extract_json_fence, validate_findings
from prevue.engines.prompt import _build_retry_prompt
from prevue.models import ReviewRequest, ReviewResult


def _degraded_result(
    prose: str,
    parse_error: str,
    req: ReviewRequest,
    start: float,
    *,
    retried: bool,
    dropped_findings: int = 0,
    model_label: str,
) -> ReviewResult:
    return ReviewResult(
        summary_markdown=prose,
        findings=[],
        degraded=True,
        dropped_findings=dropped_findings,
        engine_meta={
            "model": model_label,
            "duration_s": round(time.monotonic() - start, 1),
            "retried": retried,
            "parse_error": parse_error,
        },
    )


def review_with_retry(
    req: ReviewRequest,
    *,
    invoke: Callable[[str], str],
    secret: str,
    build_prompt: Callable[[ReviewRequest], str],
    max_prompt_bytes: int,
    model_label: str,
) -> ReviewResult:
    prompt = build_prompt(req)
    prompt_bytes = len(prompt.encode("utf-8"))
    if prompt_bytes > max_prompt_bytes:
        raise EngineFailure(
            f"Prompt exceeds 1MB ({prompt_bytes:,} bytes); use file-based fallback in Phase 6"
        )

    start = time.monotonic()
    retried = False

    stdout = invoke(prompt)
    prose, payload, fence_err = extract_json_fence(stdout)

    if fence_err:
        retry_prompt = _build_retry_prompt(prompt, fence_err)
        if len(retry_prompt.encode("utf-8")) > max_prompt_bytes:
            return _degraded_result(
                prose, fence_err, req, start, retried=False, model_label=model_label
            )

        retried = True
        try:
            stdout = invoke(retry_prompt)
        except EngineFailure:
            return _degraded_result(
                prose, fence_err, req, start, retried=True, model_label=model_label
            )

        prose, payload, fence_err = extract_json_fence(stdout)
        if fence_err:
            return _degraded_result(
                prose, fence_err, req, start, retried=True, model_label=model_label
            )

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
        },
    )
