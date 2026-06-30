---
phase: 10-boundary-contracts
reviewed: 2026-06-30T12:00:00Z
depth: standard
files_reviewed: 31
files_reviewed_list:
  - .github/scripts/install-engine-cli.sh
  - .github/workflows/prevue-review.yml
  - .github/workflows/review.yml
  - .github/workflows/update-pricing.yml
  - src/prevue/config.py
  - src/prevue/engines/claude_code_cli.py
  - src/prevue/engines/cli_adapter.py
  - src/prevue/engines/copilot_cli.py
  - src/prevue/engines/cursor_cli.py
  - src/prevue/engines/errors.py
  - src/prevue/engines/flow.py
  - src/prevue/engines/gemini_cli.py
  - src/prevue/engines/registry.py
  - src/prevue/engines/spec.py
  - src/prevue/engines/tokens.py
  - src/prevue/engines/usage.py
  - src/prevue/github/comments.py
  - src/prevue/pricing/__init__.py
  - src/prevue/pricing/model_prices.json
  - src/prevue/review.py
  - tests/fixtures/pricing/sample_prices.json
  - tests/fixtures/usage/antigravity_text.txt
  - tests/fixtures/usage/claude_envelope.json
  - tests/fixtures/usage/copilot_otel.jsonl
  - tests/fixtures/usage/cursor_envelope.json
  - tests/test_comments.py
  - tests/test_config_precedence.py
  - tests/test_copilot_adapter.py
  - tests/test_engine_contract.py
  - tests/test_model_roles.py
  - tests/test_output_contract.py
  - tests/test_pricing.py
  - tests/test_raw_args.py
  - tests/test_registry.py
  - tests/test_reusable_workflow_yaml.py
  - tests/test_usage_capture.py
findings:
  critical: 1
  warning: 0
  info: 3
  total: 4
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-30T12:00:00Z
**Depth:** standard
**Files Reviewed:** 31
**Status:** issues_found

## Summary

Iteration 3 final pass. First, independently re-verified (not trusted from the fix
report) that the iteration-2 CR-01 lint/format regression is actually resolved:
`uv run ruff check .` reports `All checks passed!`, `uv run ruff format --check .`
reports `105 files already formatted`, and `uv run pytest -q` is green at `800 passed`.
All three gates are clean on the current tree — this is a genuine fix, confirmed by
direct command execution, not by reading the diff.

With the lint/test gates clean, this iteration did a fresh adversarial pass across the
full 31-file scope rather than re-checking only the files iteration 2 touched. That pass
surfaced one new, previously-undetected **BLOCKER**: `usage._parse_copilot_otel`
(`src/prevue/engines/usage.py`) violates its own documented T-10-07 contract
("all JSON/JSONL parsing is wrapped in try/except — any parse error returns None").
The function only catches `json.JSONDecodeError`/`ValueError` around `json.loads(line)`
and `OSError` around file I/O, but does not validate that the *decoded* JSON value is a
dict before calling `.get()` on it at four separate nesting levels (the JSONL record
itself, each `resourceSpans` element, each `scopeSpans` element, each `spans` element).
A structurally-valid-but-wrong-shaped JSON line (e.g. a bare array, string, or number —
plausible from a truncated write, a future Copilot OTEL exporter format change, or
corrupted OTEL export content) raises an uncaught `AttributeError` that propagates out of
`capture_usage` and crashes the entire review run, rather than degrading gracefully to
the bytes/4 estimate as documented and as every other malformed-input path in this module
does. This was reproduced directly (not just read) with two independent minimal repros
below. No existing test in `test_usage_capture.py` exercises a non-dict-shaped decoded
JSONL line, so the gap evaded both the test suite and the prior two review iterations.

Three Info-tier items remain: two carried-forward items the user flagged as known and out
of fix-scope (`_sanitize_stderr` private alias in `copilot_cli.py`/`errors.py`;
`update-pricing.yml`'s pricing spot-check assumes dict-shaped model entries — same
root-cause class as the new CR-01 finding, just in a different file/context and lower
severity since it only affects a human-reviewed scheduled bump PR, not the live review
path), plus one new Info item: the WR-01 raw_args exhaustive scalar-rejection fix has no
committed regression test — its correctness was verified by ad hoc `uv run python` repros
across iter2/iter3/this pass, not by a test that prevents future regression.

## Critical Issues

### CR-01: `_parse_copilot_otel` crashes with uncaught `AttributeError` on non-dict-shaped OTEL JSONL records, violating the documented T-10-07 graceful-degradation contract

**File:** `src/prevue/engines/usage.py:188-217`
**Issue:**

The module docstring (lines 20-22) and the function's own docstring (line 169) both
state: "T-10-07 (DoS / malformed stdout): all JSON/JSONL parsing is wrapped in
try/except — any parse error returns None (graceful fallback to bytes/4) rather than
raising and crashing the review." The implementation only honors this for the
`json.loads()` call itself:

```python
try:
    record = json.loads(line)
except (json.JSONDecodeError, ValueError):
    # Skip malformed lines (T-10-07)
    continue
```

But `record`, and every nested element walked afterward, is used with `.get(...)`
without an `isinstance(..., dict)` (or list, for the inner loops) guard:

```python
for resource_span in record.get("resourceSpans", []):
    for scope_span in resource_span.get("scopeSpans", []):
        for span in scope_span.get("spans", []):
            attrs = {
                a["key"]: _extract_attr_value(a)
                for a in span.get("attributes", [])
                if "key" in a
            }
```

If a JSONL line decodes successfully but to a non-dict top-level value (e.g. `[1,2,3]`,
`"a string"`, `42`), `record.get(...)` raises `AttributeError: '...' object has no
attribute 'get'`. The same applies if `resourceSpans`/`scopeSpans`/`spans` contains a
non-dict element. This `AttributeError` is not caught by the inner
`except (json.JSONDecodeError, ValueError)` (wrong exception type) nor by the outer
`except OSError` (also the wrong exception type — `OSError` only wraps the
read/iteration, not the per-line `.get()` chain). The crash propagates through
`capture_usage()` → `flow.review_with_retry()` → the top-level review entrypoint,
crashing the whole review run for what was a recoverable, documented-as-tolerated
malformed-input case.

Reproduced directly:

```
>>> from prevue.engines.usage import _parse_copilot_otel
>>> import tempfile, json
>>> with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
...     f.write(json.dumps([1, 2, 3]) + "\n")
...     path = f.name
>>> _parse_copilot_otel(path)
Traceback (most recent call last):
  ...
AttributeError: 'list' object has no attribute 'get'
```

```
>>> with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
...     f.write(json.dumps({"resourceSpans": ["not-a-dict"]}) + "\n")
...     path = f.name
>>> _parse_copilot_otel(path)
Traceback (most recent call last):
  ...
AttributeError: 'str' object has no attribute 'get'
```

No test in `tests/test_usage_capture.py` exercises a non-dict-decoded JSONL line at any
of the four nesting levels — only `json.JSONDecodeError`-triggering malformed JSON
(line 195's path) and the well-formed fixture (`test_copilot_otel`) are covered, so this
gap was never caught by CI.

**Fix:** Guard each `.get()` call with an `isinstance` check (or wrap the per-line body
in a broader `try/except (AttributeError, TypeError)` consistent with the function's
documented degrade-on-any-parse-error contract):

```python
try:
    record = json.loads(line)
except (json.JSONDecodeError, ValueError):
    continue
if not isinstance(record, dict):
    continue  # T-10-07: non-dict JSON line — skip, don't crash

for resource_span in record.get("resourceSpans", []):
    if not isinstance(resource_span, dict):
        continue
    for scope_span in resource_span.get("scopeSpans", []):
        if not isinstance(scope_span, dict):
            continue
        for span in scope_span.get("spans", []):
            if not isinstance(span, dict):
                continue
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
                continue
```

Add regression tests covering: a JSONL line that decodes to a non-dict top-level value
(list/string/number), and a line whose `resourceSpans`/`scopeSpans`/`spans` array
contains a non-dict element — both should return the same result as if that line were
absent (or `None`/zero totals if it's the only line), not raise.

## Info

### IN-01: WR-01 exhaustive `raw_args` scalar rejection has no committed regression test

**File:** `tests/test_raw_args.py`
**Issue:** `EngineConfig._validate_raw_args` (config.py:126-152) rejects non-list,
non-str scalars (`int`, `float`, `bool`, `dict`, `None`) passed as `raw_args`, per the
WR-01 fix from iteration 2 (commit `5e0994e`). This behavior has been manually verified
correct across at least three review iterations via ad hoc `uv run python` REPL checks
(including this one), but `test_raw_args.py` only tests the string-rejection and
list-of-strings-acceptance paths — there is no `pytest.mark.parametrize` over
`(42, 3.14, True, {"a": 1}, None)` asserting each raises `ValidationError`. A future
refactor of `_validate_raw_args` could silently regress this path (e.g. accidentally
returning early before the per-item loop) with no test catching it.
**Fix:**
```python
@pytest.mark.parametrize("bad_value", [42, 3.14, True, {"a": 1}, None])
def test_raw_args_non_list_scalar_rejected(bad_value) -> None:
    _require_engine_config()
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EngineConfig(name="copilot-cli", raw_args=bad_value)  # type: ignore[misc]


def test_raw_args_non_string_element_rejected() -> None:
    _require_engine_config()
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match=r"raw_args\[1\]"):
        EngineConfig(name="copilot-cli", raw_args=["--flag", 42])  # type: ignore[misc]
```

### IN-02: `_sanitize_stderr` private alias exists only for back-compat import

**File:** `src/prevue/engines/copilot_cli.py:42`, `src/prevue/engines/errors.py:28`
**Issue:** `_sanitize_stderr = sanitize_stderr` is a module-level alias whose only
purpose, per the docstring, is so `test_copilot_adapter.py` can `import _sanitize_stderr`
directly. The public name `sanitize_stderr` already exists and is the canonical symbol;
the underscore-prefixed alias is dead production surface that exists solely to satisfy a
test import path. Carried forward unaddressed across all three review iterations of this
cycle — confirmed still present and still Info-tier (not a correctness issue, purely a
naming/dead-surface quality note).
**Fix:** Either update `test_copilot_adapter.py` to import `sanitize_stderr` (drop the
alias), or, if back-compat with external consumers genuinely matters, leave as-is with a
clearer comment that it is a permanent compatibility shim rather than transitional.

### IN-03: `update-pricing.yml`'s pricing spot-check assumes every model entry is a dict

**File:** `.github/workflows/update-pricing.yml:43-46`
**Issue:** `data[model].get('input_cost_per_token', 0)` assumes every value in the
top-level pricing JSON is itself a dict — the same unguarded-`.get()`-on-untyped-JSON
pattern as CR-01 above, but in the scheduled pricing-bump workflow rather than the live
review path, and gated by human review before merge (the PR is never auto-merged), so
the blast radius is a workflow-step failure with a clear traceback, not a silent
miscategorization or live-review crash. If a future LiteLLM snapshot changes the shape of
`gpt-4o` or `claude-3-5-sonnet-20241022`'s entry to a non-dict, this throws an unhandled
`AttributeError` instead of a clean assertion message. Carried forward unaddressed across
all three review iterations — not touched by any of this cycle's fixes, still accurate as
written today.
**Fix:**
```python
for model in ['gpt-4o', 'claude-3-5-sonnet-20241022']:
    if model in data:
        row = data[model]
        assert isinstance(row, dict), f'{model} entry is not an object: {type(row).__name__}'
        cost = row.get('input_cost_per_token', 0)
        assert 0 < cost < 0.01, f'Implausible input cost for {model}: {cost}'
```

---

_Reviewed: 2026-06-30T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
