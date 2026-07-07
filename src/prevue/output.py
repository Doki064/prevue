"""Versioned machine-readable review output (OUTP-05 / D-08/D-09)."""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

from prevue.models import ReviewResult

OUTPUT_SCHEMA_VERSION = "1.0"


def build_compact_output(result: ReviewResult, conclusion: str) -> dict:
    """Return the compact job-output dict for $GITHUB_OUTPUT.

    Keys: schema_version, conclusion, error_count, warning_count, info_count,
    tokens (total scalar), cost_usd (float or None).

    All values are scalars — no embedded newlines — safe for $GITHUB_OUTPUT
    key=value lines (T-10-13 / Pitfall 6).
    """
    counts: Counter = Counter()
    for finding in result.findings:
        counts[finding.severity] += 1

    token_meta = result.engine_meta.get("tokens")
    token_meta = token_meta if isinstance(token_meta, dict) else {}
    tokens_total = token_meta.get("review", 0) or 0
    classify_t = token_meta.get("classify", 0) or 0
    if classify_t:
        tokens_total = (tokens_total or 0) + classify_t

    cost_usd = token_meta.get("cost_usd")

    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "conclusion": conclusion,
        "error_count": counts.get("error", 0),
        "warning_count": counts.get("warning", 0),
        "info_count": counts.get("info", 0),
        "tokens": tokens_total,
        "cost_usd": cost_usd,
    }


def build_full_output(result: ReviewResult) -> str:
    """Return the full ReviewResult as a JSON string with schema_version injected.

    Produces ``{"schema_version": "1.0", **result.model_dump(mode="json")}``.
    The returned string is valid JSON and round-trips via ``json.loads``.
    schema_version is NOT stored on the ReviewResult model itself (D-09) — it is
    injected here into the serialized output only.
    """
    payload = {"schema_version": OUTPUT_SCHEMA_VERSION, **result.model_dump(mode="json")}
    return json.dumps(payload)


def emit_machine_output(
    result: ReviewResult,
    conclusion: str,
    output_file: str | None = None,
) -> None:
    """Write compact output to $GITHUB_OUTPUT and full JSON to a result file.

    $GITHUB_OUTPUT: writes heredoc lines for each compact key (Pitfall 6).

    Result file: always written (even when GITHUB_OUTPUT is unset) so local
    runs and artifact-upload steps both get the full JSON.  Path is resolved as:
      1. *output_file* kwarg (test injection)
      2. PREVUE_RESULT_FILE env var
      3. ``prevue-result.json`` in the current working directory
    """
    compact = build_compact_output(result, conclusion)
    full_json = build_full_output(result)

    # Write the full JSON result file (unconditional — artifact + local runs)
    if output_file is None:
        if os.environ.get("GITHUB_ACTIONS") and not os.environ.get("PREVUE_RESULT_FILE"):
            print(
                "prevue: PREVUE_RESULT_FILE not set under Actions; "
                "writing prevue-result.json to CWD",
                file=sys.stderr,
            )
        output_file = os.environ.get("PREVUE_RESULT_FILE", "prevue-result.json")
    out = Path(output_file)
    try:
        out.write_text(full_json, encoding="utf-8")
    except OSError as exc:
        # Non-fatal: log to stderr and continue — GITHUB_OUTPUT may still succeed.
        print(
            f"prevue: failed to write result file {str(out)!r}: {exc}",
            file=sys.stderr,
        )

    # Write compact lines to $GITHUB_OUTPUT (guarded — no-op when unset)
    github_output_path = os.environ.get("GITHUB_OUTPUT")
    if not github_output_path:
        return
    try:
        with open(github_output_path, "a", encoding="utf-8") as fh:
            for key, value in compact.items():
                value_str = "" if value is None else str(value)
                delimiter = f"PREVUE_DELIM_{key.upper()}"
                fh.write(f"{key}<<{delimiter}\n{value_str}\n{delimiter}\n")
    except OSError as exc:
        print(
            f"prevue: failed to write $GITHUB_OUTPUT ({github_output_path!r}): {exc}",
            file=sys.stderr,
        )
