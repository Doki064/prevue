"""Per-strategy engine usage capture (PERF-03 / D-04).

Dispatches to the appropriate capture strategy based on ``spec.usage_capture``:

  - ``stdout-json``  — Claude Code: parse the ``--output-format json`` envelope.
                       Returns real input/output/cache tokens + cost_usd with
                       ``estimated=False``.  Review text for fence extraction is
                       the envelope's ``result`` field (Pitfall 3 — raw stdout
                       is the envelope JSON, not the review text).
  - ``otel-jsonl``   — Copilot CLI: read + sum OTEL spans from the JSONL file at
                       ``otel_path`` (``COPILOT_OTEL_FILE_EXPORTER_PATH``).
                       Returns real tokens with ``estimated=False``.
                       WARNING 3: Copilot reports ``estimated=True`` until Plan 05
                       wires the env var into the workflow.  When ``otel_path`` is
                       unset / empty / missing, returns ``None`` → caller falls
                       back to ``estimate_tokens`` with ``estimated=True``.
  - ``none``         — Cursor / Antigravity: no reliable token reporting.
                       Always returns ``None`` → caller estimates with bytes/4.

T-10-07 (DoS / malformed stdout): all JSON/JSONL parsing is wrapped in
``try/except`` — any parse error returns ``None`` (graceful fallback to bytes/4)
rather than raising and crashing the review.

T-10-08 (secret leakage): only numeric token fields + cost_usd are captured.
Raw stdout is never stored in engine_meta.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prevue.engines.spec import CliEngineSpec

# OTEL attribute key names used by Copilot CLI
_OTEL_PROMPT_TOKENS = "llm.usage.prompt_tokens"
_OTEL_COMPLETION_TOKENS = "llm.usage.completion_tokens"
_OTEL_CACHE_READ_TOKENS = "llm.usage.cache_read_tokens"


def capture_usage(
    spec: CliEngineSpec,
    stdout: str,
    otel_path: str | None = None,
) -> dict[str, Any] | None:
    """Capture real token usage from engine output per the spec's strategy.

    Args:
        spec: The engine spec whose ``usage_capture`` field controls dispatch.
        stdout: Raw stdout from the engine subprocess.
        otel_path: Filesystem path to the OTEL JSONL file (used when
                   ``usage_capture == "otel-jsonl"``).  Pass
                   ``os.environ.get("COPILOT_OTEL_FILE_EXPORTER_PATH")`` from
                   the caller.  ``None`` or empty string → graceful None return.

    Returns:
        dict: Token counts + optional cost_usd, with ``estimated: False``.
              Shape: ``{"input", "output", "cache_read", "cache_creation"?,
                        "cost_usd"?, "estimated": False}``.
        None: When this engine cannot report usage (``none`` strategy) or when
              the capture source is unavailable/malformed → caller falls back to
              ``estimate_tokens`` with ``estimated=True``.
    """
    strategy = spec.usage_capture

    if strategy == "stdout-json":
        return _parse_stdout_json(stdout)
    elif strategy == "otel-jsonl":
        return _parse_copilot_otel(otel_path)
    else:
        # "none" strategy — Cursor, Antigravity: no reliable token reporting
        return None


def parse_envelope(stdout: str) -> dict[str, Any] | None:
    """Parse the Claude ``--output-format json`` envelope into a raw dict.

    Single shared JSON-parsing code path for the Claude envelope format, used
    by both ``_parse_stdout_json`` (token/cost extraction from ``usage``) and
    ``flow._resolve_fence_source`` (review-text extraction from ``result``).
    Keeping one parser avoids the two call sites silently desyncing on
    tolerance/error-handling as the envelope format evolves.

    T-10-07: wraps json.loads in try/except — returns None on any parse
    failure (malformed/non-JSON stdout) rather than raising.

    Returns:
        dict: the parsed envelope, whatever shape it has.
        None: stdout is not valid JSON, or does not decode to a dict.
    """
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(envelope, dict):
        return None
    return envelope


def _parse_stdout_json(stdout: str) -> dict[str, Any] | None:
    """Parse Claude's ``--output-format json`` envelope for real token counts.

    The envelope structure (Claude Code CLI):
    ::

        {
          "type": "result",
          "result": "<review text with possible json fence>",
          "usage": {
            "input_tokens": ...,
            "output_tokens": ...,
            "cache_read_input_tokens": ...,
            "cache_creation_input_tokens": ...
          },
          "total_cost_usd": ...
        }

    Pitfall 3: the ``result`` field is the review text; ``extract_json_fence``
    must be called on ``result``, NOT on raw stdout (which is the JSON envelope).
    This function returns the parsed envelope dict; the caller (flow.py) is
    responsible for extracting review text from ``result``.

    T-10-07: wraps json.loads in try/except (via ``parse_envelope``) — returns
    None on any parse failure.

    Returns:
        dict with ``input``, ``output``, ``cache_read``, ``cache_creation``,
        optional ``cost_usd``, and ``estimated=False``.
        None on parse failure (falls back to bytes/4 estimate).
    """
    envelope = parse_envelope(stdout)
    if envelope is None:
        # T-10-07: malformed stdout — degrade gracefully
        return None

    usage_block = envelope.get("usage")
    if not isinstance(usage_block, dict):
        return None

    result: dict[str, Any] = {
        "input": usage_block.get("input_tokens", 0) or 0,
        "output": usage_block.get("output_tokens", 0) or 0,
        "cache_read": usage_block.get("cache_read_input_tokens", 0) or 0,
        "cache_creation": usage_block.get("cache_creation_input_tokens", 0) or 0,
        "estimated": False,
    }

    # Prefer vendor-reported cost (Claude total_cost_usd) when present
    total_cost = envelope.get("total_cost_usd")
    if total_cost is not None:
        result["cost_usd"] = float(total_cost)

    return result


def _parse_copilot_otel(otel_path: str | None) -> dict[str, Any] | None:
    """Parse + sum Copilot OTEL JSONL spans for real token counts.

    Each line in the JSONL file is a resource-span object.  We walk the
    attribute list on each span and accumulate llm.usage.* token counts.

    WARNING 3 (cross-wave dependency): Copilot reports ``estimated=True``
    until Plan 05 wires ``COPILOT_OTEL_FILE_EXPORTER_PATH`` into the workflow.
    When ``otel_path`` is None / empty / missing, this function returns None
    and the engine falls back to bytes/4 (``estimated=True``).

    T-10-07: wraps all I/O and JSON parsing in try/except.

    T-01 (10-THERMOS): ``otel_path`` may be a directory (Copilot's file
    exporter writes one or more ``*.jsonl`` files under the configured
    path rather than treating it as a single file). When ``otel_path`` is
    a directory, glob and sum spans across every ``*.jsonl`` file inside
    it; when it is a file, read it directly (prior behavior unchanged).

    Returns:
        dict with summed ``input``, ``output``, ``cache_read``,
        and ``estimated=False``.
        None when path unset/missing/malformed → caller estimates.
    """
    # WARNING 3: OTEL path unset — expected until Plan 05 wires the env
    if not otel_path:
        return None

    path = Path(otel_path)
    if not path.exists():
        return None

    if path.is_dir():
        jsonl_files = sorted(path.glob("*.jsonl"))
    else:
        jsonl_files = [path]

    total_input = 0
    total_output = 0
    total_cache_read = 0

    try:
        for jsonl_file in jsonl_files:
            for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    # Skip malformed lines (T-10-07)
                    continue

                if not isinstance(record, dict):
                    # T-10-07: non-dict top-level JSON value — skip, don't crash
                    continue

                # Walk resourceSpans → scopeSpans → spans → attributes
                for resource_span in record.get("resourceSpans", []):
                    if not isinstance(resource_span, dict):
                        continue  # T-10-07: malformed resourceSpans element
                    for scope_span in resource_span.get("scopeSpans", []):
                        if not isinstance(scope_span, dict):
                            continue  # T-10-07: malformed scopeSpans element
                        for span in scope_span.get("spans", []):
                            if not isinstance(span, dict):
                                continue  # T-10-07: malformed spans element
                            attrs = {
                                a["key"]: _extract_attr_value(a)
                                for a in span.get("attributes", [])
                                if isinstance(a, dict) and "key" in a
                            }
                            try:
                                total_input += int(attrs.get(_OTEL_PROMPT_TOKENS) or 0)
                                total_output += int(attrs.get(_OTEL_COMPLETION_TOKENS) or 0)
                                total_cache_read += int(attrs.get(_OTEL_CACHE_READ_TOKENS) or 0)
                            except (TypeError, ValueError):
                                continue  # skip malformed span (T-10-07)

    except OSError:
        # T-10-07: file I/O error — degrade to None
        return None

    return {
        "input": total_input,
        "output": total_output,
        "cache_read": total_cache_read,
        "estimated": False,
    }


def _extract_attr_value(attr: dict[str, Any]) -> int | str | float | bool | None:
    """Extract the scalar value from an OTEL attribute value dict.

    OTEL attributes use ``{"key": "...", "value": {"intValue": N}}`` shapes.
    Use explicit key presence check — ``or`` suppresses falsy values (0, False, "").
    """
    value = attr.get("value", {})
    if not isinstance(value, dict):
        return None
    for key in ("intValue", "doubleValue", "stringValue", "boolValue"):
        if key in value:
            return value[key]
    return None
