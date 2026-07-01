"""RED contract tests for per-role model resolution (ENGN-09 / D-11/D-13).

These tests are intentionally RED until Plan 04 implements _resolve_engine_models()
in prevue.config. They pin the contract for per-role model resolution and verify
that merge_findings (fingerprint-deterministic merge) is preserved unchanged (D-13).

Per-role resolution (D-11):
  models.<role> if set, else engine.model, else engine default (None).
  Roles: classify, review, consolidate.
  consolidate slot resolves (D-13) but nothing consumes it until Phase 13.

Merge determinism preserved (D-13):
  merge_findings fingerprint dedup with higher-severity-wins remains unchanged.
"""

from __future__ import annotations

import pytest

# merge_findings already exists in prevue.multicall — assert it is unchanged (GREEN)
from prevue.multicall import merge_findings

try:
    from prevue.config import _resolve_engine_models

    _IMPORT_ERROR: ImportError | None = None
except ImportError as exc:
    _resolve_engine_models = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc


def _require_engine_models() -> None:
    """Fail clearly if _resolve_engine_models is not importable."""
    if _IMPORT_ERROR is not None:
        pytest.fail(
            f"prevue.config._resolve_engine_models does not exist yet "
            f"(Plan 04 will create it): {_IMPORT_ERROR}",
            pytrace=False,
        )


# ---------------------------------------------------------------------------
# _resolve_engine_models (RED until Plan 04)
# ---------------------------------------------------------------------------


def test_per_role_model_overrides_single_model() -> None:
    """models.<role> takes precedence over the single engine.model fallback."""
    _require_engine_models()
    raw = {
        "engine": {
            "name": "copilot-cli",
            "model": "gpt-5",
            "models": {
                "classify": "gpt-5-mini",
                "review": "gpt-5",
                "consolidate": "gpt-5-mini",
            },
        }
    }
    models = _resolve_engine_models(raw)  # type: ignore[misc]
    assert models["classify"] == "gpt-5-mini"
    assert models["review"] == "gpt-5"
    assert models["consolidate"] == "gpt-5-mini"


def test_single_model_fallback_when_role_unset() -> None:
    """When a role is not set in models.*, engine.model is used as fallback."""
    _require_engine_models()
    raw = {
        "engine": {
            "name": "copilot-cli",
            "model": "gpt-5",
            "models": {
                "review": "gpt-5-turbo",
                # classify and consolidate not set -> should fall back to engine.model
            },
        }
    }
    models = _resolve_engine_models(raw)  # type: ignore[misc]
    assert models["review"] == "gpt-5-turbo"
    assert models["classify"] == "gpt-5"  # fallback to engine.model
    assert models["consolidate"] == "gpt-5"  # fallback to engine.model


def test_all_roles_fallback_to_engine_model() -> None:
    """When no models.* block, all roles fall back to engine.model."""
    _require_engine_models()
    raw = {"engine": {"name": "copilot-cli", "model": "gpt-4o"}}
    models = _resolve_engine_models(raw)  # type: ignore[misc]
    assert models["classify"] == "gpt-4o"
    assert models["review"] == "gpt-4o"
    assert models["consolidate"] == "gpt-4o"


def test_all_roles_none_when_no_model_set() -> None:
    """When no engine.model and no models.*, all roles resolve to None."""
    _require_engine_models()
    raw = {"engine": {"name": "copilot-cli"}}
    models = _resolve_engine_models(raw)  # type: ignore[misc]
    assert models["classify"] is None
    assert models["review"] is None
    assert models["consolidate"] is None


def test_consolidate_resolves_but_not_consumed() -> None:
    """D-13: consolidate slot resolves in config but nothing consumes it this phase."""
    _require_engine_models()
    raw = {
        "engine": {
            "model": "gpt-5",
            "models": {"consolidate": "gpt-5-mini"},
        }
    }
    models = _resolve_engine_models(raw)  # type: ignore[misc]
    # Must resolve without error (slot is reserved)
    assert "consolidate" in models
    assert models["consolidate"] == "gpt-5-mini"


# ---------------------------------------------------------------------------
# merge_findings determinism preserved (GREEN — D-13: must stay unchanged)
# ---------------------------------------------------------------------------


def _make_finding(**kwargs):
    """Build a Finding-like dict for merge_findings testing."""
    from prevue.models import Finding

    return Finding(
        path=kwargs.get("path", "src/app.py"),
        line=kwargs.get("line", 10),
        side=kwargs.get("side", "RIGHT"),
        severity=kwargs.get("severity", "warning"),
        title=kwargs.get("title", "Issue title"),
        body=kwargs.get("body", "Issue body"),
        suggestion=kwargs.get("suggestion", None),
    )


def _make_result(findings):
    """Build a ReviewResult-like object for merge_findings."""
    from prevue.models import ReviewResult

    return ReviewResult(
        summary_markdown="summary",
        findings=findings,
    )


def test_merge_findings_dedup_by_fingerprint() -> None:
    """merge_findings deduplicates identical-fingerprint findings (D-13: unchanged)."""
    f1 = _make_finding(severity="warning", title="Null pointer", path="a.py", line=5)
    f2 = _make_finding(severity="warning", title="Null pointer", path="a.py", line=5)
    result = merge_findings([_make_result([f1]), _make_result([f2])])
    assert len(result) == 1, "Duplicate findings must be deduplicated"


def test_merge_findings_higher_severity_wins() -> None:
    """merge_findings: error beats warning on same fingerprint (D-13: unchanged)."""
    warning = _make_finding(severity="warning", title="Same issue", path="b.py", line=20)
    error = _make_finding(severity="error", title="Same issue", path="b.py", line=20)
    result = merge_findings([_make_result([warning]), _make_result([error])])
    assert len(result) == 1
    assert result[0].severity == "error", "Higher severity must win on fingerprint collision"


def test_merge_findings_different_locations_kept() -> None:
    """merge_findings keeps findings at different locations (no false dedup)."""
    f1 = _make_finding(title="Issue", path="c.py", line=1)
    f2 = _make_finding(title="Issue", path="c.py", line=2)
    result = merge_findings([_make_result([f1, f2])])
    assert len(result) == 2, "Different lines must not be merged"
