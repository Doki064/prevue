"""RED contract tests for per-engine usage capture strategies (PERF-03).

These tests are intentionally RED until Plan 03 implements prevue.engines.usage.
They pin the behavioral contract for capture_usage() so downstream implementation
must satisfy the exact shape asserted here.

Strategy matrix (from 10-RESEARCH.md Per-Engine Token Reporting Matrix):
  - Claude Code: stdout-json envelope -> real tokens, estimated=False
  - Cursor: stdout JSON but no token fields -> None -> caller estimates
  - Copilot: OTEL JSONL file -> sum per-call tokens, estimated=False
  - Antigravity: plain text, no reliable token reporting -> None -> caller estimates
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    from prevue.engines.usage import capture_usage

    _IMPORT_ERROR: ImportError | None = None
except ImportError as exc:
    capture_usage = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "usage"


def _require_import() -> None:
    """Fail the calling test with a clear RED message if the module is not available."""
    if _IMPORT_ERROR is not None:
        pytest.fail(
            f"prevue.engines.usage is not importable yet (Plan 03 will create it): {_IMPORT_ERROR}",
            pytrace=False,
        )


class _FakeSpec:
    """Minimal spec stub for unit tests — mirrors the usage_capture field of CliEngineSpec."""

    def __init__(self, usage_capture: str) -> None:
        self.usage_capture = usage_capture


def test_claude_stdout_json() -> None:
    """Claude stdout-json envelope: real tokens captured, estimated=False."""
    _require_import()
    spec = _FakeSpec("stdout-json")
    envelope = (FIXTURES_DIR / "claude_envelope.json").read_text()

    result = capture_usage(spec, stdout=envelope)  # type: ignore[misc]

    assert result is not None, "Claude stdout-json must return a usage dict, not None"
    assert result["estimated"] is False, "Claude real tokens are not estimated"
    assert result["input"] == 1500
    assert result["output"] == 250
    assert result["cache_read"] == 800
    # cache_creation is present in the fixture (200) — capture must surface it or at minimum
    # not crash on its presence.
    assert "input" in result
    assert "output" in result


def test_claude_stdout_json_prefers_total_cost_usd() -> None:
    """When Claude envelope includes total_cost_usd, capture must surface it."""
    _require_import()
    spec = _FakeSpec("stdout-json")
    envelope = (FIXTURES_DIR / "claude_envelope.json").read_text()
    data = json.loads(envelope)
    expected_cost = data["total_cost_usd"]  # 0.007125

    result = capture_usage(spec, stdout=envelope)  # type: ignore[misc]

    assert result is not None
    # cost_usd must be the vendor-reported cost, not recomputed
    assert "cost_usd" in result
    assert abs(result["cost_usd"] - expected_cost) < 1e-10


def test_fallback_estimated_cursor() -> None:
    """Cursor stdout-json has no token fields: capture returns None (caller uses bytes/4)."""
    _require_import()
    spec = _FakeSpec("none")
    envelope = (FIXTURES_DIR / "cursor_envelope.json").read_text()

    result = capture_usage(spec, stdout=envelope)  # type: ignore[misc]

    assert result is None, (
        "capture_usage must return None for 'none' strategy so caller falls back to estimate"
    )


def test_fallback_estimated_antigravity() -> None:
    """Antigravity plain-text output: capture returns None (caller uses bytes/4)."""
    _require_import()
    spec = _FakeSpec("none")
    text = (FIXTURES_DIR / "antigravity_text.txt").read_text()

    result = capture_usage(spec, stdout=text)  # type: ignore[misc]

    assert result is None, "capture_usage must return None for 'none' strategy on plain text output"


def test_copilot_otel(tmp_path: Path) -> None:
    """Copilot OTEL JSONL: parse + sum per-call tokens from fixture, estimated=False."""
    _require_import()
    spec = _FakeSpec("otel-jsonl")
    # Copy fixture to tmp_path to simulate COPILOT_OTEL_FILE_EXPORTER_PATH
    otel_fixture = FIXTURES_DIR / "copilot_otel.jsonl"
    otel_path = tmp_path / "copilot-usage.jsonl"
    otel_path.write_bytes(otel_fixture.read_bytes())

    # The fixture has 2 JSONL lines:
    #   line 1: input=1200, output=180, cache_read=600
    #   line 2: input=900,  output=120, cache_read=450
    # Summed: input=2100, output=300, cache_read=1050
    result = capture_usage(spec, stdout="", otel_path=str(otel_path))  # type: ignore[misc]

    assert result is not None, "Copilot OTEL must return a usage dict, not None"
    assert result["estimated"] is False, "Copilot OTEL tokens are real (not estimated)"
    assert result["input"] == 2100
    assert result["output"] == 300
    assert result["cache_read"] == 1050


def test_otel_missing_path_returns_none() -> None:
    """If OTEL path is missing/None for otel-jsonl strategy, capture gracefully returns None."""
    _require_import()
    spec = _FakeSpec("otel-jsonl")

    result = capture_usage(spec, stdout="", otel_path=None)  # type: ignore[misc]

    assert result is None, "Missing OTEL path must degrade gracefully to None"
