"""Shared retry-then-degrade review flow for all engine adapters (D-08)."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from prevue.engines.errors import EngineFailure
from prevue.engines.parsing import extract_json_fence, validate_findings
from prevue.engines.prompt import _build_retry_prompt
from prevue.engines.tokens import estimate_tokens
from prevue.engines.usage import capture_usage
from prevue.models import ReviewRequest, ReviewResult

if TYPE_CHECKING:
    from prevue.engines.spec import CliEngineSpec


@dataclass
class InvocationResult:
    """Bundle from one invoke+capture+fence-extract pass."""

    raw_stdout: str
    captured: dict[str, Any] | None
    prose: str
    payload: list | dict | None
    fence_err: str | None
    fence_source: str


def _estimated_cost_usd(
    input_tokens: int,
    output_tokens: int,
    spec: CliEngineSpec | None,
    model_label: str | None,
    pricing_override: dict | None,
) -> float | None:
    """Best-effort estimated cost when no real usage capture is available."""
    if spec is None or not model_label or model_label == "default":
        return None
    from prevue.pricing import compute_cost

    try:
        return compute_cost(
            spec.name,
            model_label,
            {"input": input_tokens, "output": output_tokens},
            override=pricing_override,
        )
    except (TypeError, ValueError):
        # ponytail: defense in depth — config-load validation (CR-01) should
        # already reject non-numeric pricing rows, but degrade to "unknown
        # cost" instead of crashing the review if a bad row slips through.
        return None


def _token_meta(
    prompt: str,
    stdout: str = "",
    captured: dict[str, Any] | None = None,
    *,
    spec: CliEngineSpec | None = None,
    model_label: str | None = None,
    pricing_override: dict | None = None,
) -> dict[str, int | bool]:
    """Build the token-meta dict for a single-invocation (no retry) flow.

    When *captured* is provided (from capture_usage), the real token counts are
    embedded and ``estimated`` is taken from the capture.  When None, falls back
    to bytes/4 with ``estimated=True`` (labeled fallback — D-04); T-07 also
    attaches a best-effort ``~est`` cost_usd via _estimated_cost_usd when
    *spec*/*model_label* are known (e.g. cursor-cli, antigravity-cli).
    """
    prompt_tokens = estimate_tokens(prompt)
    stdout_tokens = estimate_tokens(stdout)
    review_tokens = prompt_tokens + stdout_tokens
    if captured is not None:
        meta: dict[str, Any] = {}
        meta.update(_pick_real_token_fields(captured))
        real_review = (captured.get("input") or 0) + (captured.get("output") or 0)
        meta["review"] = real_review if real_review else review_tokens
        return meta
    meta = {"review": review_tokens, "estimated": True}
    cost = _estimated_cost_usd(prompt_tokens, stdout_tokens, spec, model_label, pricing_override)
    if cost is not None:
        meta["cost_usd"] = cost
    return meta


def _retry_token_meta(
    prompt: str,
    retry_prompt: str,
    first_stdout: str,
    retry_stdout: str,
    captured: dict[str, Any] | None = None,
    captured_retry: dict[str, Any] | None = None,
    *,
    spec: CliEngineSpec | None = None,
    model_label: str | None = None,
    pricing_override: dict | None = None,
    both_required: bool = False,
) -> dict[str, int | bool]:
    """Sum both invocations without double-counting the embedded original prompt.

    When capture dicts are provided, real token counts are used; otherwise the
    bytes/4 fallback applies (``estimated=True``); T-07 also attaches a
    best-effort ``~est`` cost_usd when *spec*/*model_label* are known.
    Per-engine flag — not global. *both_required* is forwarded to
    ``_sum_real_token_fields`` (see its docstring).
    """
    prompt_tokens = estimate_tokens(prompt) + estimate_tokens(retry_prompt)
    output_tokens = estimate_tokens(first_stdout) + estimate_tokens(retry_stdout)
    review_tokens = prompt_tokens + output_tokens
    # Sum both invocations' real captures — `captured_retry or captured` dropped the first.
    if captured is not None or captured_retry is not None:
        meta: dict[str, Any] = {}
        summed = _sum_real_token_fields(captured, captured_retry, both_required=both_required)
        meta.update(summed)
        real_review = (summed.get("input") or 0) + (summed.get("output") or 0)
        meta["review"] = real_review if real_review else review_tokens
        return meta
    meta = {"review": review_tokens, "estimated": True}
    cost = _estimated_cost_usd(prompt_tokens, output_tokens, spec, model_label, pricing_override)
    if cost is not None:
        meta["cost_usd"] = cost
    return meta


def _pick_real_token_fields(captured: dict[str, Any]) -> dict[str, Any]:
    """Extract the real-token fields from a capture dict for embedding in token-meta."""
    result: dict[str, Any] = {"estimated": captured.get("estimated", False)}
    for key in ("input", "output", "cache_read", "cache_creation", "cost_usd"):
        if key in captured:
            result[key] = captured[key]
    return result


def _sum_real_token_fields(
    captured: dict[str, Any] | None,
    captured_retry: dict[str, Any] | None,
    *,
    both_required: bool = False,
) -> dict[str, Any]:
    """Sum real-token fields across both retry invocations.

    ``both_required`` marks the total as an estimate when only one side is
    present. Only correct for independent per-invocation captures — a
    cumulative capture (e.g. OTEL) intentionally passes one side as None
    because the other side's total already includes it.
    """
    result: dict[str, Any] = {
        "estimated": both_required and (captured is None or captured_retry is None)
    }
    for key in ("input", "output", "cache_read", "cache_creation", "cost_usd"):
        v1 = (captured or {}).get(key)
        v2 = (captured_retry or {}).get(key)
        if v1 is None and v2 is None:
            continue
        result[key] = (v1 or 0) + (v2 or 0)
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


def _enrich_capture(
    spec: CliEngineSpec | None,
    stdout: str,
    model_label: str,
    pricing_override: dict | None,
    otel_path: str | None,
) -> dict[str, Any] | None:
    """Capture real usage and attach cost_usd if not vendor-reported."""
    if spec is None:
        return None
    captured = capture_usage(spec, stdout, otel_path=otel_path)
    if (
        captured is not None
        and "cost_usd" not in captured
        and model_label
        and model_label != "default"
    ):
        from prevue.pricing import compute_cost

        try:
            priced = compute_cost(spec.name, model_label, captured, override=pricing_override)
        except (TypeError, ValueError):
            # ponytail: defense in depth — see _estimated_cost_usd's matching
            # guard; config-load validation (CR-01) is the primary defense.
            priced = None
        if priced is not None:
            captured["cost_usd"] = priced
    return captured


def _run_invocation(
    prompt: str,
    invoke: Callable[[str], str],
    spec: CliEngineSpec | None,
    model_label: str,
    pricing_override: dict | None,
    otel_path: str | None,
) -> InvocationResult:
    """Run one invoke() call and return the invoke+capture+fence-extract bundle."""
    raw_stdout = invoke(prompt)
    captured = _enrich_capture(spec, raw_stdout, model_label, pricing_override, otel_path)
    fence_source = _resolve_fence_source(spec, raw_stdout)
    prose, payload, fence_err = extract_json_fence(fence_source)
    return InvocationResult(
        raw_stdout=raw_stdout,
        captured=captured,
        prose=prose,
        payload=payload,
        fence_err=fence_err,
        fence_source=fence_source,
    )


def _otel_capture_grew(
    first_captured: dict[str, Any] | None,
    retry_captured: dict[str, Any] | None,
) -> bool:
    """True unless the retry OTEL read failed to pick up new spans (shared-path model)."""
    if first_captured is None:
        return True
    if retry_captured is None:
        return False
    return any(
        (retry_captured.get(key) or 0) != (first_captured.get(key) or 0)
        for key in ("input", "output", "cache_read", "cache_creation")
    )


def _partial_estimate_retry_tokens(
    retry_prompt: str,
    retry_stdout: str,
    first_captured: dict[str, Any],
    *,
    spec: CliEngineSpec | None,
    model_label: str | None,
    pricing_override: dict | None,
) -> dict[str, int | bool]:
    """First invocation's real capture plus bytes/4 estimate for a stuck retry OTEL read."""
    est_input = estimate_tokens(retry_prompt)
    est_output = estimate_tokens(retry_stdout)
    real_input = first_captured.get("input") or 0
    real_output = first_captured.get("output") or 0
    total_input = real_input + est_input
    total_output = real_output + est_output
    meta: dict[str, Any] = {
        "estimated": True,
        "input": total_input,
        "output": total_output,
        "review": total_input + total_output,
    }
    for key in ("cache_read", "cache_creation"):
        if key in first_captured:
            meta[key] = first_captured[key]
    real_cost = first_captured.get("cost_usd")
    est_cost = _estimated_cost_usd(est_input, est_output, spec, model_label, pricing_override)
    if real_cost is not None or est_cost is not None:
        meta["cost_usd"] = (real_cost or 0) + (est_cost or 0)
    return meta


def _merge_retry_tokens(
    prompt: str,
    retry_prompt: str,
    first: InvocationResult,
    retry: InvocationResult | None,
    *,
    otel_accumulates: bool,
    spec: CliEngineSpec | None,
    model_label: str,
    pricing_override: dict | None,
) -> dict[str, int | bool]:
    """Compute the final tokens dict for a (possibly retried) review."""
    if retry is None:
        return _token_meta(
            prompt,
            first.fence_source,
            first.captured,
            spec=spec,
            model_label=model_label,
            pricing_override=pricing_override,
        )

    # Shared OTEL path: directory is cumulative; avoid double-counting first spans.
    if (
        otel_accumulates
        and first.captured is not None
        and not _otel_capture_grew(first.captured, retry.captured)
    ):
        return _partial_estimate_retry_tokens(
            retry_prompt,
            retry.fence_source,
            first.captured,
            spec=spec,
            model_label=model_label,
            pricing_override=pricing_override,
        )

    captured_for_sum = None if otel_accumulates else first.captured
    return _retry_token_meta(
        prompt,
        retry_prompt,
        first.fence_source,
        retry.fence_source,
        captured_for_sum,
        retry.captured,
        spec=spec,
        model_label=model_label,
        pricing_override=pricing_override,
        both_required=not otel_accumulates,
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
    pricing_override: dict | None = None,
    otel_path: str | None = None,
    retry_otel_path: str | None = None,
) -> ReviewResult:
    """Run the review flow with one optional retry on fence-parse failure.

    When *spec* is provided, real per-engine token usage is captured via
    ``usage.capture_usage`` and the ``estimated`` flag is set per-engine
    (D-04, PERF-03).  When None, falls back to bytes/4 estimates throughout.

    *otel_path*: per-call OTEL directory for copilot-cli (isolates max_review_calls > 1).
    *retry_otel_path*: distinct path for the retry attempt when supplied.
    """
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
    if otel_path is None and spec is not None and spec.usage_capture == "otel-jsonl":
        otel_path = os.environ.get("COPILOT_OTEL_FILE_EXPORTER_PATH") or None
    if retry_otel_path is None:
        retry_otel_path = otel_path

    start = time.monotonic()
    retried = False
    retry_prompt = ""
    retry: InvocationResult | None = None
    _otel_accumulates = (
        spec is not None and spec.usage_capture == "otel-jsonl" and retry_otel_path == otel_path
    )

    first = _run_invocation(prompt, invoke, spec, model_label, pricing_override, otel_path)
    prose, payload, fence_err = first.prose, first.payload, first.fence_err

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
                tokens=_merge_retry_tokens(
                    prompt,
                    retry_prompt,
                    first,
                    None,
                    otel_accumulates=_otel_accumulates,
                    spec=spec,
                    model_label=model_label,
                    pricing_override=pricing_override,
                ),
            )

        retried = True
        try:
            raw_retry_stdout = invoke(retry_prompt)
        except EngineFailure:
            # Retry input was sent but produced no output before failing.
            empty_retry = InvocationResult(
                raw_stdout="",
                captured=None,
                prose=prose,
                payload=None,
                fence_err=fence_err,
                fence_source="",
            )
            return _degraded_result(
                prose,
                fence_err,
                req,
                start,
                retried=True,
                model_label=model_label,
                tokens=_merge_retry_tokens(
                    prompt,
                    retry_prompt,
                    first,
                    empty_retry,
                    otel_accumulates=_otel_accumulates,
                    spec=spec,
                    model_label=model_label,
                    pricing_override=pricing_override,
                ),
            )

        _enriched_retry_capture = _enrich_capture(
            spec, raw_retry_stdout, model_label, pricing_override, retry_otel_path
        )
        fence_retry_source = _resolve_fence_source(spec, raw_retry_stdout)
        prose, payload, fence_err = extract_json_fence(fence_retry_source)
        retry = InvocationResult(
            raw_stdout=raw_retry_stdout,
            captured=_enriched_retry_capture,
            prose=prose,
            payload=payload,
            fence_err=fence_err,
            fence_source=fence_retry_source,
        )

        if fence_err:
            return _degraded_result(
                prose,
                fence_err,
                req,
                start,
                retried=True,
                model_label=model_label,
                tokens=_merge_retry_tokens(
                    prompt,
                    retry_prompt,
                    first,
                    retry,
                    otel_accumulates=_otel_accumulates,
                    spec=spec,
                    model_label=model_label,
                    pricing_override=pricing_override,
                ),
            )

    def _tokens() -> dict[str, int | bool]:
        return _merge_retry_tokens(
            prompt,
            retry_prompt,
            first,
            retry,
            otel_accumulates=_otel_accumulates,
            spec=spec,
            model_label=model_label,
            pricing_override=pricing_override,
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

    For json_envelope engines, unwrap the ``result`` field first (Pitfall 3).
    """
    from prevue.engines.usage import unwrap_envelope_result

    return unwrap_envelope_result(spec, raw_stdout)
