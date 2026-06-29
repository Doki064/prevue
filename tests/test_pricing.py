"""RED contract tests for cost computation (PERF-03 / D-05/D-06).

These tests are intentionally RED until Plan 03 implements prevue.pricing.
They pin the behavioral contract for compute_cost() and load_pricing_table()
so downstream implementation must satisfy the exact shape asserted here.

Formula (from 10-RESEARCH.md § Cost Computation):
  cost = input_tokens          * input_cost_per_token
       + output_tokens         * output_cost_per_token
       + cache_read_tokens     * cache_read_input_token_cost      (when present)
       + cache_creation_tokens * cache_creation_input_token_cost  (when present)

D-06c: consumer engine.pricing override takes precedence over vendored table.
When Claude already returns total_cost_usd, prefer it over recomputation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    from prevue.pricing import compute_cost, load_pricing_table

    _IMPORT_ERROR: ImportError | None = None
except ImportError as exc:
    compute_cost = None  # type: ignore[assignment]
    load_pricing_table = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc

PRICING_FIXTURE = Path(__file__).parent / "fixtures" / "pricing" / "sample_prices.json"


def _require_import() -> None:
    """Fail the calling test with a clear RED message if the module is not available."""
    if _IMPORT_ERROR is not None:
        pytest.fail(
            f"prevue.pricing is not importable yet (Plan 03 will create it): {_IMPORT_ERROR}",
            pytrace=False,
        )


def _sample_table() -> dict:
    """Load the small sample pricing table fixture (not the full 500 KB snapshot)."""
    return json.loads(PRICING_FIXTURE.read_text())


# ---------------------------------------------------------------------------
# load_pricing_table
# ---------------------------------------------------------------------------


def test_load_pricing_table_returns_dict() -> None:
    """load_pricing_table(path) returns a dict keyed by model id."""
    _require_import()
    table = load_pricing_table(str(PRICING_FIXTURE))  # type: ignore[misc]
    assert isinstance(table, dict)
    assert "claude-3-5-sonnet-20241022" in table
    assert "gpt-4o" in table


# ---------------------------------------------------------------------------
# compute_cost — basic formula
# ---------------------------------------------------------------------------


def test_basic_input_output_cost() -> None:
    """input+output cost computed correctly for a model with no cache fields."""
    _require_import()
    table = _sample_table()
    usage = {"input": 1000, "output": 200, "cache_read": 0, "cache_creation": 0, "estimated": False}

    cost = compute_cost("openai", "gpt-4o", usage, table=table)  # type: ignore[misc]

    # gpt-4o: 2.5e-6 per input, 1e-5 per output
    expected = 1000 * 2.5e-6 + 200 * 1e-5
    assert cost is not None
    assert abs(cost - expected) < 1e-12


def test_cache_aware_formula() -> None:
    """Cache read + creation costs are included when present in the pricing table."""
    _require_import()
    table = _sample_table()
    usage = {
        "input": 1500,
        "output": 250,
        "cache_read": 800,
        "cache_creation": 200,
        "estimated": False,
    }

    cost = compute_cost("anthropic", "claude-3-5-sonnet-20241022", usage, table=table)  # type: ignore[misc]

    # claude-3-5-sonnet: input=3e-6, output=1.5e-5, cache_read=3e-7, cache_creation=3.75e-6
    expected = 1500 * 3e-6 + 250 * 1.5e-5 + 800 * 3e-7 + 200 * 3.75e-6
    assert cost is not None
    assert abs(cost - expected) < 1e-12


def test_unknown_model_returns_none() -> None:
    """An unrecognized model key returns None (no cost, labeled) — not an error."""
    _require_import()
    table = _sample_table()
    usage = {"input": 1000, "output": 100, "cache_read": 0, "cache_creation": 0, "estimated": False}

    cost = compute_cost("unknown-engine", "totally-unknown-model-xyz", usage, table=table)  # type: ignore[misc]

    assert cost is None, "Unknown model must return None, not raise or return 0"


def test_override_takes_precedence_over_table() -> None:
    """D-06c: engine.pricing override map beats the vendored table for matching model."""
    _require_import()
    table = _sample_table()
    # Override gpt-4o with completely different pricing
    override = {
        "gpt-4o": {
            "input_cost_per_token": 9.99e-6,
            "output_cost_per_token": 9.99e-5,
        }
    }
    usage = {"input": 1000, "output": 100, "cache_read": 0, "cache_creation": 0, "estimated": False}

    cost = compute_cost("openai", "gpt-4o", usage, override=override, table=table)  # type: ignore[misc]

    expected_override = 1000 * 9.99e-6 + 100 * 9.99e-5
    expected_table = 1000 * 2.5e-6 + 100 * 1e-5
    assert cost is not None
    # Must use override, not table
    assert abs(cost - expected_override) < 1e-12
    assert abs(cost - expected_table) > 1e-10, "Override must differ from table value"


def test_prefers_total_cost_usd_when_present() -> None:
    """When usage dict includes cost_usd (from Claude envelope), prefer it over recomputation."""
    _require_import()
    table = _sample_table()
    usage = {
        "input": 1500,
        "output": 250,
        "cache_read": 800,
        "cache_creation": 200,
        "estimated": False,
        "cost_usd": 0.007125,  # vendor-reported by Claude
    }

    cost = compute_cost("anthropic", "claude-3-5-sonnet-20241022", usage, table=table)  # type: ignore[misc]

    # Must prefer vendor cost, not recompute from token counts
    assert cost is not None
    assert abs(cost - 0.007125) < 1e-10


def test_estimated_usage_still_computes_cost() -> None:
    """Even when usage is estimated (estimated=True), cost is computed and returned."""
    _require_import()
    table = _sample_table()
    usage = {"input": 5000, "output": 800, "cache_read": 0, "cache_creation": 0, "estimated": True}

    cost = compute_cost("openai", "gpt-4o", usage, table=table)  # type: ignore[misc]

    # Should still compute (caller may want an estimated cost)
    assert cost is not None
    assert cost > 0


def test_zero_tokens_returns_zero_cost() -> None:
    """Zero token usage returns zero cost (not None)."""
    _require_import()
    table = _sample_table()
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0, "estimated": False}

    cost = compute_cost("openai", "gpt-4o", usage, table=table)  # type: ignore[misc]

    assert cost is not None
    assert cost == 0.0
