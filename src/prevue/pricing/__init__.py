"""prevue.pricing — vendored pricing snapshot + pure cost computation.

Source: BerriAI/litellm model_prices_and_context_window.json
Vendored: 2026-06-29
URL: https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json

Never fetched at review time (D-06a). The pinned snapshot is committed under
src/prevue/pricing/model_prices.json and ships in the wheel.
Auto-update: see .github/workflows/update-pricing.yml (D-06b, scheduled bump PR).
Consumer override: engine.pricing in prevue.yml takes precedence (D-06c).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

__all__ = ["compute_cost", "load_pricing_table"]

# ---------------------------------------------------------------------------
# Pricing table loader — reads vendored JSON from package dir (D-06a)
# ---------------------------------------------------------------------------

_BUNDLED_JSON = Path(__file__).parent / "model_prices.json"


def load_pricing_table(path: str | None = None) -> dict[str, Any]:
    """Load a pricing table from *path* (or the vendored snapshot when None).

    The result is cached for the bundled default path. Test code should always
    pass the small ``sample_prices.json`` fixture via *path* — no pytest test
    should call the zero-arg form against the full 500 KB snapshot (WARNING 2).

    Args:
        path: Optional filesystem path to a pricing JSON file.  When omitted,
              the vendored ``model_prices.json`` inside this package is used.

    Returns:
        dict: Model-keyed pricing table (LiteLLM field names).
    """
    if path is None:
        return _load_bundled()
    return json.loads(Path(path).read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def _load_bundled() -> dict[str, Any]:
    """Cached loader for the vendored bundled snapshot (zero-arg default)."""
    return json.loads(_BUNDLED_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Cost computation — pure, cache-aware, override-aware, table-injectable
# ---------------------------------------------------------------------------

_INPUT_FIELD = "input_cost_per_token"
_OUTPUT_FIELD = "output_cost_per_token"
_CACHE_READ_FIELD = "cache_read_input_token_cost"
_CACHE_CREATE_FIELD = "cache_creation_input_token_cost"


def _normalize_model(model: str) -> str:
    """Lowercase + strip common provider prefixes for table lookup."""
    model = model.lower().strip()
    # Strip common provider prefix notation (e.g. "anthropic/claude-..." → "claude-...")
    for prefix in (
        "anthropic/",
        "openai/",
        "google/",
        "vertex_ai/",
        "azure/",
        "bedrock/",
    ):
        if model.startswith(prefix):
            model = model[len(prefix) :]
            break
    return model


def _lookup_row(
    model: str,
    override: dict[str, Any] | None,
    table: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the pricing row for *model*, honouring override precedence (D-06c).

    The override map is checked first; falls back to the pricing table.
    Tries exact key, then normalized key.  Returns None when absent from both.
    """
    # D-06c: engine.pricing override takes precedence
    if override:
        if model in override:
            return override[model]
        norm = _normalize_model(model)
        if norm in override:
            return override[norm]

    # Vendored / injected table
    if model in table:
        return table[model]
    norm = _normalize_model(model)
    if norm in table:
        return table[norm]

    return None


def compute_cost(
    engine: str,  # noqa: ARG001 — future use (per-engine override key)
    model: str,
    usage: dict[str, Any],
    override: dict[str, Any] | None = None,
    table: dict[str, Any] | None = None,
) -> float | None:
    """Compute the dollar cost for a single review invocation.

    Formula (cache-aware, LiteLLM field names):
      cost = input_tokens          * input_cost_per_token
           + output_tokens         * output_cost_per_token
           + cache_read_tokens     * cache_read_input_token_cost      (when present)
           + cache_creation_tokens * cache_creation_input_token_cost  (when present)

    Shortcut: when *usage* carries a non-None ``cost_usd`` (Claude's
    ``total_cost_usd``), that vendor-reported value is returned verbatim
    without recomputing from token counts.

    Args:
        engine: Engine name (reserved for future per-engine override keying).
        model: Model identifier (e.g. ``"claude-3-5-sonnet-20241022"``).
        usage: Token counts dict with keys ``input``, ``output``,
               ``cache_read``, ``cache_creation``, optional ``cost_usd``,
               ``estimated``.
        override: Optional ``engine.pricing`` map from ``prevue.yml``
                  (D-06c).  Row for *model* in this map shadows the table.
        table: Pricing table dict (defaults to the vendored snapshot via
               ``load_pricing_table()`` when None).  Inject the small fixture
               in all pytest tests (WARNING 2 — never use the default in tests).

    Returns:
        float: Computed cost in USD (may be 0.0 for zero-token usage).
        None:  Unknown model — no cost, labeled by caller.
    """
    # Prefer vendor-reported cost (Claude total_cost_usd) over recomputation
    cost_usd = usage.get("cost_usd")
    if cost_usd is not None:
        return float(cost_usd)

    if table is None:
        table = load_pricing_table()

    row = _lookup_row(model, override, table)
    if row is None:
        return None  # unknown model → no cost, caller labels

    input_tokens = usage.get("input", 0) or 0
    output_tokens = usage.get("output", 0) or 0
    cache_read = usage.get("cache_read", 0) or 0
    cache_creation = usage.get("cache_creation", 0) or 0

    cost = 0.0
    cost += input_tokens * (row.get(_INPUT_FIELD) or 0.0)
    cost += output_tokens * (row.get(_OUTPUT_FIELD) or 0.0)
    cost += cache_read * (row.get(_CACHE_READ_FIELD) or 0.0)
    cost += cache_creation * (row.get(_CACHE_CREATE_FIELD) or 0.0)
    return cost
