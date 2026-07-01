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
from prevue.engines.usage import capture_usage
from prevue.models import ReviewRequest, ReviewResult

if TYPE_CHECKING:
    from prevue.engines.spec import CliEngineSpec


def _estimated_cost_usd(
    input_tokens: int,
    output_tokens: int,
    spec: CliEngineSpec | None,
    model_label: str | None,
    pricing_override: dict | None,
) -> float | None:
    """Best-effort ~est cost for engines with no real usage capture (T-07 — 10-THERMOS).

    cursor-cli / antigravity-cli (``usage_capture == "none"``) never return a
    real ``captured`` dict, so cost_usd was never computed for them — tokens
    showed in the sticky comment but cost silently didn't, an inconsistent UX.
    Feeds the bytes/4 estimate split (prompt ≈ input, stdout ≈ output) into the
    same ``compute_cost`` pricing table used for real captures; the caller
    labels the result ``~est`` via the existing ``estimated`` flag.

    Returns None when spec/model are unknown or the model has no pricing row
    (same "unknown model → no cost" contract as ``compute_cost``).
    """
    if spec is None or not model_label or model_label == "default":
        return None
    from prevue.pricing import compute_cost

    return compute_cost(
        spec.name,
        model_label,
        {"input": input_tokens, "output": output_tokens},
        override=pricing_override,
    )


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
) -> dict[str, int | bool]:
    """Sum both invocations without double-counting the embedded original prompt.

    When capture dicts are provided, real token counts are used; otherwise the
    bytes/4 fallback applies (``estimated=True``); T-07 also attaches a
    best-effort ``~est`` cost_usd when *spec*/*model_label* are known.
    Per-engine flag — not global.
    """
    prompt_tokens = estimate_tokens(prompt) + estimate_tokens(retry_prompt)
    output_tokens = estimate_tokens(first_stdout) + estimate_tokens(retry_stdout)
    review_tokens = prompt_tokens + output_tokens
    # T-04 (10-THERMOS): sum both invocations' real captures instead of picking
    # one — `captured_retry or captured` previously discarded the first call's
    # real input/output/cache/cost when both invocations succeeded, silently
    # under-reporting ~50% of actual usage on any retried review.
    if captured is not None or captured_retry is not None:
        meta: dict[str, Any] = {}
        summed = _sum_real_token_fields(captured, captured_retry)
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
) -> dict[str, Any]:
    """Sum real-token fields across both retry invocations (T-04 — 10-THERMOS).

    Unlike ``_pick_real_token_fields`` (single capture), this combines both
    captures so a retried review reports its true total usage/cost instead of
    only one invocation's numbers. A field is summed when present in either
    capture. Caller guarantees at least one capture is not None, so
    ``estimated`` is always False here (capture_usage never returns a dict
    with ``estimated=True`` — that value is synthesized only by the
    no-capture-at-all fallback in the caller).
    """
    result: dict[str, Any] = {"estimated": False}
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
    """Capture real usage and attach cost_usd if not vendor-reported (Q-05, 10-THERMOS).

    Extracted from the two identical capture+cost blocks in review_with_retry
    (first invocation and retry). Returns the enriched capture dict or None.
    """
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

        priced = compute_cost(spec.name, model_label, captured, override=pricing_override)
        if priced is not None:
            captured["cost_usd"] = priced
    return captured


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
) -> ReviewResult:
    """Run the review flow with one optional retry on fence-parse failure.

    When *spec* is provided, real per-engine token usage is captured via
    ``usage.capture_usage`` and the ``estimated`` flag is set per-engine
    (D-04, PERF-03).  When None, falls back to bytes/4 estimates throughout.

    Pitfall 3: for ``stdout-json`` engines (Claude Code), raw stdout is a JSON
    envelope; ``extract_json_fence`` must run on the ``result`` field, not raw
    stdout — otherwise every Claude review degrades to "no fence found".
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
    otel_path: str | None = None
    if spec is not None and spec.usage_capture == "otel-jsonl":
        otel_path = os.environ.get("COPILOT_OTEL_FILE_EXPORTER_PATH") or None

    start = time.monotonic()
    retried = False
    retry_prompt = ""

    raw_stdout = invoke(prompt)

    # Capture real usage from the first invocation (PERF-03, D-04, Q-05)
    captured = _enrich_capture(spec, raw_stdout, model_label, pricing_override, otel_path)

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
                tokens=_token_meta(
                    prompt,
                    first_stdout,
                    captured,
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
            return _degraded_result(
                prose,
                fence_err,
                req,
                start,
                retried=True,
                model_label=model_label,
                tokens=_retry_token_meta(
                    prompt,
                    retry_prompt,
                    first_stdout,
                    "",
                    captured,
                    spec=spec,
                    model_label=model_label,
                    pricing_override=pricing_override,
                ),
            )

        # Capture usage for retry invocation too (Q-05).
        # otel-jsonl: the JSONL dir accumulates spans from ALL invocations, so
        # captured_retry already contains first+retry spans. Pass captured=None
        # to _retry_token_meta to avoid double-counting first invocation's spans.
        _otel_accumulates = spec is not None and spec.usage_capture == "otel-jsonl"
        captured_retry = _enrich_capture(
            spec, raw_retry_stdout, model_label, pricing_override, otel_path
        )
        captured_for_sum = None if _otel_accumulates else captured

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
                    prompt,
                    retry_prompt,
                    first_stdout,
                    retry_stdout,
                    captured_for_sum,
                    captured_retry,
                    spec=spec,
                    model_label=model_label,
                    pricing_override=pricing_override,
                ),
            )

        def _tokens() -> dict[str, int | bool]:
            return _retry_token_meta(
                prompt,
                retry_prompt,
                first_stdout,
                retry_stdout,
                captured_for_sum,
                captured_retry,
                spec=spec,
                model_label=model_label,
                pricing_override=pricing_override,
            )

    else:
        retry_stdout = ""

        def _tokens() -> dict[str, int | bool]:
            return _token_meta(
                prompt,
                first_stdout,
                captured,
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

    For json_envelope engines (Claude Code, Cursor CLI): raw stdout is a JSON
    envelope whose ``result`` field holds the review text. Running
    extract_json_fence on the envelope JSON would fail — Pitfall 3.

    Q-03 (10-THERMOS): now keyed on ``spec.stdout_format == "json_envelope"``
    instead of ``spec.usage_capture == "stdout-json"`` — the two axes are
    independent. Cursor produces a JSON envelope (stdout_format="json_envelope")
    but has no capturable token usage (usage_capture="none").

    Guard: if raw_stdout cannot be parsed as JSON or has no ``result`` field,
    fall back to raw_stdout so the normal degraded path fires gracefully.

    T-09b (10-THERMOS quick task): delegates to the single shared
    ``usage.unwrap_envelope_result`` helper — this and
    ``cli_adapter._unwrap_classify_text`` cannot silently desync on
    JSON-parse tolerance (WR-02) since both call the same function.
    """
    from prevue.engines.usage import unwrap_envelope_result

    return unwrap_envelope_result(spec, raw_stdout)
