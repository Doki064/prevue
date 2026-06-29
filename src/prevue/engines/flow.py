"""Shared retry-then-degrade review flow for all engine adapters (D-08)."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from prevue.engines.errors import EngineFailure
from prevue.engines.parsing import extract_json_fence, validate_findings
from prevue.engines.prompt import _build_retry_prompt
from prevue.engines.tokens import estimate_tokens
from prevue.models import ReviewRequest, ReviewResult

if TYPE_CHECKING:
    from prevue.engines.spec import CliEngineSpec


def _token_meta(
    prompt: str,
    stdout: str = "",
    captured: dict[str, Any] | None = None,
) -> dict[str, int | bool]:
    """Build the token-meta dict for a single-invocation (no retry) flow.

    When *captured* is provided (from capture_usage), the real token counts are
    embedded and ``estimated`` is taken from the capture.  When None, falls back
    to bytes/4 with ``estimated=True`` (labeled fallback — D-04).
    """
    review_tokens = estimate_tokens(prompt) + estimate_tokens(stdout)
    if captured is not None:
        meta: dict[str, Any] = {"review": review_tokens}
        meta.update(_pick_real_token_fields(captured))
        return meta
    return {
        "review": review_tokens,
        "estimated": True,
    }


def _retry_token_meta(
    prompt: str,
    retry_prompt: str,
    first_stdout: str,
    retry_stdout: str,
    captured: dict[str, Any] | None = None,
    captured_retry: dict[str, Any] | None = None,
) -> dict[str, int | bool]:
    """Sum both invocations without double-counting the embedded original prompt.

    When capture dicts are provided, real token counts are used; otherwise the
    bytes/4 fallback applies (``estimated=True``).  Per-engine flag — not global.
    """
    review_tokens = (
        estimate_tokens(prompt)
        + estimate_tokens(first_stdout)
        + estimate_tokens(retry_prompt)
        + estimate_tokens(retry_stdout)
    )
    # Prefer captured real tokens from the first invocation (or retry if first absent)
    best_capture = captured_retry or captured
    if best_capture is not None:
        meta: dict[str, Any] = {"review": review_tokens}
        meta.update(_pick_real_token_fields(best_capture))
        return meta
    return {
        "review": review_tokens,
        "estimated": True,
    }


def _pick_real_token_fields(captured: dict[str, Any]) -> dict[str, Any]:
    """Extract the real-token fields from a capture dict for embedding in token-meta."""
    result: dict[str, Any] = {"estimated": captured.get("estimated", False)}
    for key in ("input", "output", "cache_read", "cache_creation", "cost_usd"):
        if key in captured:
            result[key] = captured[key]
    return result


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
    spec: CliEngineSpec | None = None,
) -> ReviewResult:
    """Run the review flow with one optional retry on fence-parse failure.

    When *spec* is provided, real per-engine token usage is captured via
    ``usage.capture_usage`` and the ``estimated`` flag is set per-engine
    (D-04, PERF-03).  When None, falls back to bytes/4 estimates throughout.

    Pitfall 3: for ``stdout-json`` engines (Claude Code), raw stdout is a JSON
    envelope; ``extract_json_fence`` must run on the ``result`` field, not raw
    stdout — otherwise every Claude review degrades to "no fence found".
    """
    from prevue.engines.usage import capture_usage

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

    # Determine OTEL log path for copilot (WARNING 3: None until Plan 05 wires the env)
    otel_path: str | None = None
    if spec is not None and spec.usage_capture == "otel-jsonl":
        otel_path = os.environ.get("COPILOT_OTEL_FILE_EXPORTER_PATH") or None

    start = time.monotonic()
    retried = False
    retry_prompt = ""

    raw_stdout = invoke(prompt)

    # Capture real usage from the first invocation (PERF-03, D-04)
    captured: dict[str, Any] | None = None
    if spec is not None:
        captured = capture_usage(spec, raw_stdout, otel_path=otel_path)

    # Pitfall 3: for stdout-json engines, the fence lives inside the "result" field.
    # Guard: if stdout is not JSON or has no "result", fall back to raw stdout path.
    fence_source = _resolve_fence_source(spec, raw_stdout)
    prose, payload, fence_err = extract_json_fence(fence_source)

    first_stdout = fence_source  # used for token-meta size accounting

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
                tokens=_token_meta(prompt, first_stdout, captured),
            )

        retried = True
        try:
            raw_retry_stdout = invoke(retry_prompt)
        except EngineFailure:
            # Retry input was sent but produced no output before failing.
            return _degraded_result(
                prose,
                fence_err,
                req,
                start,
                retried=True,
                model_label=model_label,
                tokens=_retry_token_meta(prompt, retry_prompt, first_stdout, "", captured),
            )

        # Capture usage for retry invocation too
        captured_retry: dict[str, Any] | None = None
        if spec is not None:
            captured_retry = capture_usage(spec, raw_retry_stdout, otel_path=otel_path)

        fence_retry_source = _resolve_fence_source(spec, raw_retry_stdout)
        prose, payload, fence_err = extract_json_fence(fence_retry_source)
        retry_stdout = fence_retry_source

        if fence_err:
            return _degraded_result(
                prose,
                fence_err,
                req,
                start,
                retried=True,
                model_label=model_label,
                tokens=_retry_token_meta(
                    prompt, retry_prompt, first_stdout, retry_stdout, captured, captured_retry
                ),
            )

        def _tokens() -> dict[str, int | bool]:
            return _retry_token_meta(
                prompt, retry_prompt, first_stdout, retry_stdout, captured, captured_retry
            )

    else:
        retry_stdout = ""

        def _tokens() -> dict[str, int | bool]:
            return _token_meta(prompt, first_stdout, captured)

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


def _resolve_fence_source(spec: CliEngineSpec | None, raw_stdout: str) -> str:
    """Return the text to run extract_json_fence on.

    For stdout-json engines (Claude Code): raw stdout is a JSON envelope whose
    ``result`` field holds the review text (with the markdown fence inside it).
    Running extract_json_fence on the envelope JSON would fail — Pitfall 3.

    Guard: if raw_stdout cannot be parsed as JSON or has no ``result`` field,
    fall back to raw_stdout so the normal degraded path fires gracefully.
    """
    if spec is None or spec.usage_capture != "stdout-json":
        return raw_stdout

    try:
        envelope = __import__("json").loads(raw_stdout)
        result_text = envelope.get("result")
        if isinstance(result_text, str):
            return result_text
    except (ValueError, AttributeError):
        pass

    # Guard: non-JSON stdout or missing result → degrade via raw path
    return raw_stdout
