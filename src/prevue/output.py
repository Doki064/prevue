"""Versioned machine-readable review output (OUTP-05 / D-08/D-09).

Q-01 (10-THERMOS): extracted from review.py — these helpers have no
dependency on the review orchestration flow (classify/diff/GitHub calls);
they only transform a finished ReviewResult into the compact $GITHUB_OUTPUT
dict and the full JSON artifact. review.py was growing past the >1k-line
rule with output formatting mixed into orchestration logic.
"""

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
        sev = getattr(finding, "severity", None)
        if sev is not None:
            counts[str(sev)] += 1

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

    $GITHUB_OUTPUT: writes ``key=value`` lines for each compact key.  When a
    value could theoretically be multiline, the GitHub heredoc form is used
    (``name<<DELIM\\nvalue\\nDELIM``).  In practice compact values are all
    scalars so the simple form is safe; we use the heredoc form as
    belt-and-suspenders (T-10-13 — GitHub-documented safe pattern).

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
    # WR-04: warn when PREVUE_RESULT_FILE is an absolute path outside RUNNER_TEMP.
    # In production the workflow sets it to ${{ runner.temp }}/prevue-result.json;
    # a misconfigured or unexpected value gets a diagnostic on stderr rather than
    # silently writing to an arbitrary location.
    runner_temp = os.environ.get("RUNNER_TEMP")
    if runner_temp and out.is_absolute() and not str(out).startswith(runner_temp):
        print(
            f"prevue: PREVUE_RESULT_FILE {str(out)!r} is outside RUNNER_TEMP"
            f" ({runner_temp!r}); proceeding",
            file=sys.stderr,
        )
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
                # Heredoc form for safety (T-10-13): GitHub-documented pattern for
                # values that could contain newlines; compact values are scalars but
                # we use it unconditionally as belt-and-suspenders.
                delimiter = f"PREVUE_DELIM_{key.upper()}"
                fh.write(f"{key}<<{delimiter}\n{value_str}\n{delimiter}\n")
    except OSError as exc:
        # T-06 (10-THERMOS): non-fatal — GITHUB_OUTPUT write errors must not abort
        # the review — but a silent `pass` made consumer-side debugging impossible
        # (job outputs just look empty with no clue why). Log to stderr instead,
        # matching the PREVUE_RESULT_FILE diagnostic pattern above.
        print(
            f"prevue: failed to write $GITHUB_OUTPUT ({github_output_path!r}): {exc}",
            file=sys.stderr,
        )
