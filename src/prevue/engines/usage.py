"""Per-strategy engine usage capture (PERF-03 / D-04).

Dispatches to the appropriate capture strategy based on ``spec.usage_capture``:

  - ``stdout-json``  — Claude Code: parse the ``--output-format json`` envelope.
                       Returns real input/output/cache tokens + cost_usd with
                       ``estimated=False``.  Review text for fence extraction is
                       the envelope's ``result`` field (Pitfall 3 — raw stdout
                       is the envelope JSON, not the review text).
  - ``otel-jsonl``   — Copilot CLI: read + sum OTEL spans from the JSONL file(s)
                       at ``otel_path`` (``COPILOT_OTEL_FILE_EXPORTER_PATH``).
                       Returns real tokens with ``estimated=False``.  Each line
                       is a FLAT record (``{"type": "span"|"metric",
                       "attributes": {...}}``) — see ``_parse_copilot_otel`` for
                       the real schema — see ``_parse_copilot_otel``.
                       When ``otel_path`` is unset / empty / missing / contains
                       no real span records, returns ``None`` → caller falls
                       back to ``estimate_tokens`` with ``estimated=True``.
  - ``none``         — Cursor / Antigravity: no reliable token reporting.
                       Always returns ``None`` → caller estimates with bytes/4.

Malformed JSON/JSONL degrades to None (bytes/4 fallback). Only numeric token
fields and cost_usd are captured — raw stdout is never stored in engine_meta.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prevue.engines.spec import CliEngineSpec


def unwrap_envelope_result(spec: CliEngineSpec | None, raw_stdout: str) -> str:
    """Unwrap stdout_format=json_envelope payloads; return raw_stdout on failure."""
    if spec is None or spec.stdout_format != "json_envelope":
        return raw_stdout

    envelope = parse_envelope(raw_stdout)
    if envelope is not None:
        result_text = envelope.get("result")
        if isinstance(result_text, str):
            return result_text

    return raw_stdout


# OTEL attribute key names used by the real Copilot CLI file exporter (flat
# per-line ``attributes`` dict — see _parse_copilot_otel docstring).
_OTEL_INPUT_TOKENS = "gen_ai.usage.input_tokens"
_OTEL_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
_OTEL_CACHE_READ_TOKENS = "gen_ai.usage.cache_read.input_tokens"
_OTEL_CACHE_CREATION_TOKENS = "gen_ai.usage.cache_creation.input_tokens"


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

    Returns None on parse failure.
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

    Returns None on parse failure.
    """
    envelope = parse_envelope(stdout)
    if envelope is None:
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
    """Parse and sum Copilot CLI OTEL file-exporter JSONL for real token counts.

    Each line is a flat record: ``{"type": "span", "attributes": {...}}``.
    Non-span records are skipped. Cost is derived later via ``pricing.compute_cost``.

    When *otel_path* is a directory, glob ``*.jsonl`` inside it.
    """
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
    total_cache_creation = 0
    span_count = 0

    try:
        for jsonl_file in jsonl_files:
            for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                if not isinstance(record, dict):
                    continue

                if record.get("type") != "span":
                    # Metric-typed (or unknown/missing type) records carry no
                    # per-call token attributes — skip, don't mis-sum.
                    continue

                attrs = record.get("attributes")
                if not isinstance(attrs, dict):
                    # Missing/null/malformed attributes (e.g. old list shape) — skip.
                    continue

                # Parse all four fields into locals first — only merge into the
                # running totals (and count the span) if the whole span parses
                # cleanly, so one malformed field can't produce a corrupted
                # partial total that still gets reported as estimated=False.
                try:
                    span_input = int(attrs.get(_OTEL_INPUT_TOKENS, 0) or 0)
                    span_output = int(attrs.get(_OTEL_OUTPUT_TOKENS, 0) or 0)
                    span_cache_read = int(attrs.get(_OTEL_CACHE_READ_TOKENS, 0) or 0)
                    span_cache_creation = int(attrs.get(_OTEL_CACHE_CREATION_TOKENS, 0) or 0)
                except (TypeError, ValueError):
                    continue

                span_count += 1
                total_input += span_input
                total_output += span_output
                total_cache_read += span_cache_read
                total_cache_creation += span_cache_creation

    except OSError:
        return None

    if span_count == 0:
        return None

    return {
        "input": total_input,
        "output": total_output,
        "cache_read": total_cache_read,
        "cache_creation": total_cache_creation,
        "estimated": False,
    }
