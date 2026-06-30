"""RED contract tests for versioned machine-readable output (OUTP-05 / D-08/D-09).

These tests are intentionally RED until Plan 05 implements the emit helpers
in prevue.review. They pin the behavioral contract for build_compact_output()
and build_full_output() so downstream implementation must satisfy the shape here.

Contract (from 10-RESEARCH.md § Pattern 4: Versioned both-form output):
  Compact form: {schema_version, conclusion, error_count, warning_count,
                 info_count, tokens, cost_usd}
  Full form:    {"schema_version": "1.0", **ReviewResult.model_dump(mode="json")}
  Both forms include schema_version="1.0" (D-09).
  GITHUB_OUTPUT rendering: each key=value line safe (no embedded newlines in a
  single value), using a heredoc-style or escaped form (Pitfall 6).
"""

from __future__ import annotations

import json

import pytest

from prevue.models import DiffBundle, Finding, ReviewResult

try:
    from prevue.review import build_compact_output, build_full_output, emit_machine_output

    _IMPORT_ERROR: ImportError | None = None
except ImportError as exc:
    build_compact_output = None  # type: ignore[assignment]
    build_full_output = None  # type: ignore[assignment]
    emit_machine_output = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc


def _require_emit_helpers() -> None:
    """Fail clearly if emit helpers are not importable."""
    if _IMPORT_ERROR is not None:
        pytest.fail(
            f"prevue.review.build_compact_output / build_full_output do not exist yet "
            f"(Plan 05 will create them): {_IMPORT_ERROR}",
            pytrace=False,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_diff() -> DiffBundle:
    return DiffBundle(
        pr_number=42,
        base_sha="abc" * 13 + "d",  # 40-char sha
        head_sha="def" * 13 + "0",
        files=[],
    )


def _make_finding(severity: str = "error") -> Finding:
    return Finding(
        path="src/app.py",
        line=10,
        severity=severity,  # type: ignore[arg-type]
        title="Test finding",
        body="A test finding body",
    )


def _make_result(findings=None, degraded=False) -> ReviewResult:
    return ReviewResult(
        summary_markdown="## Summary\n\nTest summary.",
        findings=findings or [],
        degraded=degraded,
        dropped_findings=0,
        engine_meta={"tokens": {"review": 1500, "estimated": False}},
    )


# ---------------------------------------------------------------------------
# Compact output (OUTP-05 D-08)
# ---------------------------------------------------------------------------


def test_compact_has_schema_version_and_counts() -> None:
    """build_compact_output returns schema_version='1.0' and severity counts."""
    _require_emit_helpers()
    result = _make_result(
        findings=[
            _make_finding("error"),
            _make_finding("warning"),
            _make_finding("warning"),
            _make_finding("info"),
        ]
    )
    compact = build_compact_output(result, conclusion="failure")  # type: ignore[misc]

    assert compact["schema_version"] == "1.0", "Compact must include schema_version='1.0' (D-09)"
    assert compact["conclusion"] == "failure"
    assert compact["error_count"] == 1
    assert compact["warning_count"] == 2
    assert compact["info_count"] == 1
    assert "tokens" in compact
    assert "cost_usd" in compact


def test_compact_schema_version_is_string() -> None:
    """schema_version must be a string, not a number (D-09 serialization contract)."""
    _require_emit_helpers()
    result = _make_result()
    compact = build_compact_output(result, conclusion="success")  # type: ignore[misc]
    assert isinstance(compact["schema_version"], str)
    assert compact["schema_version"] == "1.0"


def test_compact_conclusion_values() -> None:
    """Compact conclusion must be one of the gate conclusion values."""
    _require_emit_helpers()
    for conclusion in ("success", "failure", "neutral"):
        result = _make_result()
        compact = build_compact_output(result, conclusion=conclusion)  # type: ignore[misc]
        assert compact["conclusion"] == conclusion


# ---------------------------------------------------------------------------
# Full output (OUTP-05 D-08/D-09)
# ---------------------------------------------------------------------------


def test_full_is_parseable_json_with_findings() -> None:
    """build_full_output returns a JSON string that round-trips with findings included."""
    _require_emit_helpers()
    findings = [_make_finding("error"), _make_finding("warning")]
    result = _make_result(findings=findings)

    full_json = build_full_output(result)  # type: ignore[misc]

    # Must be valid JSON
    parsed = json.loads(full_json)
    assert isinstance(parsed, dict), "Full output must be a JSON object"
    assert "findings" in parsed, "Full output must include findings"
    assert len(parsed["findings"]) == 2
    assert parsed["schema_version"] == "1.0", "Full output must include schema_version='1.0'"


def test_full_output_schema_version_present() -> None:
    """Full output includes schema_version='1.0' at the top level (D-09)."""
    _require_emit_helpers()
    result = _make_result()
    full_json = build_full_output(result)  # type: ignore[misc]
    parsed = json.loads(full_json)
    assert "schema_version" in parsed
    assert parsed["schema_version"] == "1.0"


def test_full_output_includes_summary_markdown() -> None:
    """Full output contains summary_markdown from ReviewResult."""
    _require_emit_helpers()
    result = _make_result()
    full_json = build_full_output(result)  # type: ignore[misc]
    parsed = json.loads(full_json)
    assert "summary_markdown" in parsed


# ---------------------------------------------------------------------------
# $GITHUB_OUTPUT safety (Pitfall 6 / D-08)
# ---------------------------------------------------------------------------


def test_github_output_lines_are_safe() -> None:
    """build_compact_output values must not contain raw embedded newlines.

    $GITHUB_OUTPUT key=value format breaks if a value contains a literal newline
    (Actions truncates or errors). Either escape to \\n or use the heredoc form.
    The compact dict is designed to carry only scalar values — assert each value
    in the compact form has no unescaped newline when serialized as key=value.
    """
    _require_emit_helpers()
    result = _make_result(
        findings=[_make_finding("error")],
    )
    compact = build_compact_output(result, conclusion="failure")  # type: ignore[misc]

    for key, value in compact.items():
        value_str = str(value)
        assert "\n" not in value_str, (
            f"Compact output key '{key}' contains a raw newline — unsafe for $GITHUB_OUTPUT. "
            "Use a scalar value or escape newlines."
        )


def test_compact_tokens_field_is_numeric() -> None:
    """tokens field in compact output is a number (not a nested dict)."""
    _require_emit_helpers()
    result = _make_result()
    compact = build_compact_output(result, conclusion="success")  # type: ignore[misc]
    assert isinstance(compact["tokens"], (int, float)), (
        "tokens in compact output must be a scalar number for $GITHUB_OUTPUT safety"
    )


# ---------------------------------------------------------------------------
# emit_machine_output: result file write + $GITHUB_OUTPUT no-op when unset
# ---------------------------------------------------------------------------


def test_emit_machine_output_writes_result_file(tmp_path) -> None:
    """emit_machine_output writes valid full JSON to the result file path."""
    _require_emit_helpers()
    result = _make_result(findings=[_make_finding("error")])
    out_file = str(tmp_path / "prevue-result.json")

    emit_machine_output(result, conclusion="failure", output_file=out_file)  # type: ignore[misc]

    content = (tmp_path / "prevue-result.json").read_text(encoding="utf-8")
    parsed = json.loads(content)
    assert parsed["schema_version"] == "1.0", "Full JSON must include schema_version='1.0'"
    assert "findings" in parsed
    assert len(parsed["findings"]) == 1


def test_emit_machine_output_noop_github_output_when_unset(tmp_path, monkeypatch) -> None:
    """emit_machine_output does NOT raise when GITHUB_OUTPUT is unset (local runs)."""
    _require_emit_helpers()
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    result = _make_result()
    out_file = str(tmp_path / "prevue-result.json")

    # Must not raise; must still write the result file
    emit_machine_output(result, conclusion="success", output_file=out_file)  # type: ignore[misc]

    content = (tmp_path / "prevue-result.json").read_text(encoding="utf-8")
    parsed = json.loads(content)
    assert parsed["schema_version"] == "1.0"


def test_emit_machine_output_logs_github_output_write_failure(
    tmp_path, monkeypatch, capsys
) -> None:
    """T-06 (10-THERMOS): a GITHUB_OUTPUT write failure (e.g. path is a directory,
    permission denied) must not raise — but must be logged to stderr, not silently
    swallowed, so consumers can debug why job outputs are empty."""
    _require_emit_helpers()
    bad_github_output = tmp_path / "github_output_dir"
    bad_github_output.mkdir()  # opening a directory for append raises OSError
    monkeypatch.setenv("GITHUB_OUTPUT", str(bad_github_output))
    result = _make_result()
    out_file = str(tmp_path / "prevue-result.json")

    # Must not raise; result file still written
    emit_machine_output(result, conclusion="success", output_file=out_file)  # type: ignore[misc]

    assert (tmp_path / "prevue-result.json").exists()
    err = capsys.readouterr().err
    assert "GITHUB_OUTPUT" in err and str(bad_github_output) in err
