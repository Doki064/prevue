---
phase: 10-boundary-contracts
reviewed: 2026-06-30T00:00:00Z
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
  warning: 2
  info: 2
  total: 5
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-30T00:00:00Z
**Depth:** standard
**Files Reviewed:** 31
**Status:** issues_found

## Summary

Re-verified all 5 findings from the prior review cycle (CR-01 antigravity
`$_AGY_PROMPT` quoting, CR-02 pricing_override threading, WR-01 missing `gemini-api-key`
secret, WR-02 stderr warning for unset `PREVUE_RESULT_FILE`, WR-03 raw_args non-string
validation). All five hold up under direct testing: the antigravity shell-quoting fix was
verified with a live injection attempt against a mock `agy` binary (no command
substitution executes, prompt delivered as a literal argument); `EngineConfig.raw_args`
was verified at runtime to reject `None`/int list elements with `ValidationError`;
`pricing_override` is now threaded end-to-end from `config.engine_config.pricing` through
`CliEngineAdapter.set_pricing_override` into both `compute_cost` call sites in `flow.py`;
the dogfood `review.yml` now forwards `gemini-api-key`; and `emit_machine_output` now warns
to stderr when `PREVUE_RESULT_FILE` is unset under Actions.

A fresh full-suite run (`uv run pytest -q`) surfaced one currently-failing test that is a
genuine new regression, not a stale/pre-existing failure: commit `85c97fe` ("CR-03 refresh
inline comment body on any content change", itself part of this review cycle's fix batch)
replaced the severity-gated inline-comment update check in `post_inline_review` with an
unconditional body-diff comparison. That silently breaks the documented D-06
"rephrase-at-same-line" contract that `review.py`'s `_open_set_findings` depends on to keep
the sticky summary table and the live GitHub inline comment in sync. This is a BLOCKER —
the suite is red (1 failed, 799 passed) and the underlying behavior is a real correctness
bug, not just a stale test assertion. Two WARNING-level robustness/clarity gaps and two
INFO-level quality notes round out the rest of the pass; no new security issues were found
beyond what the prior cycle already remediated.

## Critical Issues

### CR-01: `post_inline_review` violates the documented D-06 rephrase-at-same-line contract, breaking `test_rephrase_at_same_line_keeps_inline_unchanged`

**File:** `src/prevue/github/comments.py:871-873`
**Issue:**

Commit `85c97fe` ("fix(10): CR-03 refresh inline comment body on any content change", part
of this same review cycle) replaced:

```python
if _inline_severity_changed(prior.body or "", finding.severity):
    to_update.append((prior, body, finding))
```

with:

```python
# Update on any content change, not just severity change
if prior.body != body:
    to_update.append((prior, body, finding))
```

This makes `_inline_severity_changed` (still defined at `comments.py:322-332`, with a
docstring explicitly describing the D-06 contract: *"keeps the existing comment as-is per
D-06 rather than churning it unconditionally on every run"*) dead code — it is no longer
called anywhere in `post_inline_review`.

The change directly contradicts `review.py`'s `_open_set_findings` (lines 252-302), which
implements the "rephrase-at-same-line" rule on purpose: when a carried prior at
`(path, line, side)` has a *different* fingerprint than the current engine finding at the
same location (engine rephrased the title) but severity is unchanged, the **sticky**
Findings table is built to keep showing the OLD (prior) title — by design, so the sticky
table and the live inline GitHub PR comment stay consistent (see the long comment at
`review.py:251-259` and `review.py:285-297`). With the current `comments.py` code,
`post_inline_review` now overwrites the live inline comment body with the **new**
rephrased title on every run, even though the sticky table still shows the old title for
that same finding. The two surfaces silently diverge on every PR where an LLM engine
produces a slightly different title for the same underlying issue across runs (a common
occurrence with non-deterministic LLM output) — undermining the consistency guarantee the
gate logic was specifically built to provide.

This is independently confirmed by the test suite, which is **currently failing on this
branch**:

```
$ uv run pytest tests/test_comments.py::TestPostInlineReview::test_rephrase_at_same_line_keeps_inline_unchanged -q
FAILED tests/test_comments.py::TestPostInlineReview::test_rephrase_at_same_line_keeps_inline_unchanged
AssertionError: Expected 'edit' to not have been called. Called 1 times.
```

`uv run pytest -q` across the whole repo shows exactly this 1 failure (799 passed, 1
failed) — not a pre-existing/unrelated failure.

**Fix:** Restore the severity-gated update check so D-06 rephrase-at-same-line is honored,
while still fixing the original CR-03 problem (a pure severity-string comparison missed
legitimate body-only refreshes for the *same* fingerprint, e.g. suggestion-text edits). The
correct fix is to gate on whether the new finding's fingerprint matches what the prior
comment encodes, not merely on raw body bytes:

```python
from prevue.fingerprint import fingerprint

for finding in gate.inline:
    body = render_inline_comment(finding)
    key = inline_location_key(finding.path, finding.line, finding.side)
    prior_comments = existing.get(key, [])
    if prior_comments:
        prior = prior_comments[0]
        prior_title = _parse_title_from_inline_body(prior.body or "")
        same_fingerprint = (
            prior_title is not None
            and fingerprint(finding.path, prior_title) == fingerprint(finding.path, finding.title)
        )
        if same_fingerprint:
            # Same logical finding re-emitted: refresh on any content change (CR-03
            # intent — e.g. suggestion/body text edits for the SAME finding).
            if prior.body != body:
                to_update.append((prior, body, finding))
        elif _inline_severity_changed(prior.body or "", finding.severity):
            # Rephrase-at-same-line (D-06): different fingerprint, same location.
            # Only refresh on severity escalation/de-escalation; otherwise leave the
            # live comment alone so sticky and inline stay consistent.
            to_update.append((prior, body, finding))
        if len(prior_comments) > 1:
            to_delete.extend(prior_comments[1:])
        continue
    to_create.append({...})
```

At minimum, re-run `uv run pytest tests/test_comments.py -q` and confirm
`test_rephrase_at_same_line_keeps_inline_unchanged` passes alongside the rest of
`TestPostInlineReview` before merging.

## Warnings

### WR-01: `_validate_raw_args` falls through silently for non-list, non-string scalar types

**File:** `src/prevue/config.py:126-146`
**Issue:** The validator correctly rejects a bare string and rejects a list containing
non-string elements (the WR-03 fix from the prior cycle, re-verified working in this pass).
However, if `engine.raw_args` in `prevue.yml` is some other scalar type — e.g. an int,
float, bool, or a nested dict — none of the `isinstance(value, str)` /
`isinstance(value, list)` branches match, and the function falls through to `return value`
unchanged at line 146. Pydantic then attempts to coerce that value against the outer
`list[str]` field type, which does raise (Pydantic v2 doesn't silently coerce `42` into a
list), so the request still fails — but with a generic Pydantic type-mismatch message
rather than the clean, actionable D-10 error the rest of the validator produces for the
str/list-of-non-str cases.
**Fix:** Make the validator exhaustive — reject anything that is not a `list` explicitly:

```python
@field_validator("raw_args", mode="before")
@classmethod
def _validate_raw_args(cls, value: object) -> list[str]:
    if isinstance(value, str):
        raise ValueError(
            "engine.raw_args must be a list of strings (D-10: no shell string allowed). "
            f"Got str: {value!r}"
        )
    if not isinstance(value, list):
        raise ValueError(
            f"engine.raw_args must be a list of strings, got {type(value).__name__!r}: {value!r}"
        )
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(
                f"engine.raw_args[{i}] must be a string, got {type(item).__name__!r}: {item!r}"
            )
    return value
```

### WR-02: `_resolve_fence_source` independently re-parses the Claude JSON envelope that `capture_usage` already parsed

**File:** `src/prevue/engines/flow.py:166, 266-288` and `src/prevue/engines/usage.py:77-130`
**Issue:** For `stdout-json` engines, `review_with_retry` calls `capture_usage(spec,
raw_stdout, ...)` (which internally does `json.loads(stdout)` inside
`_parse_stdout_json`), then immediately calls `_resolve_fence_source(spec, raw_stdout)`,
which performs its own *second*, independent parse of the same string via
`__import__("json").loads(raw_stdout)`. The two parsers also diverge slightly in
philosophy: `_parse_stdout_json` returns `None` whenever `usage` is missing or not a
dict, even if `result` parsed fine, while `_resolve_fence_source` ignores `usage`
entirely and only cares about `result`. That divergence is actually the desired behavior
today (fence extraction should not depend on usage metadata being present), so this is not
a live correctness bug — but the duplicated JSON-parsing logic, living in two different
modules with two different error-handling styles (one uses `except (json.JSONDecodeError,
ValueError)`, the other uses a bare `except (ValueError, AttributeError)` around a
dynamically imported `json` module), is a maintenance hazard: a future tightening or
loosening of one parser's tolerance could silently desync the two paths without any test
catching it, since both currently happen to agree on all known fixtures.
**Fix:** Factor a single `_parse_envelope(stdout: str) -> dict | None` helper (returning
the raw parsed dict, or `None` on any parse failure) shared by both
`usage._parse_stdout_json` and `flow._resolve_fence_source`, so there is exactly one
JSON-parsing code path for the Claude envelope format. Also replace the dynamic
`__import__("json")` in `_resolve_fence_source` with a normal top-level `import json` in
`flow.py` — there is no functional reason to defer that import, and it makes the function
harder to read for no benefit.

## Info

### IN-01: `update-pricing.yml`'s pricing spot-check assumes every model entry is a dict

**File:** `.github/workflows/update-pricing.yml:43-46`
**Issue:** `data[model].get('input_cost_per_token', 0)` assumes every value in the
top-level pricing JSON is itself a dict. The vendored `model_prices.json` already contains
at least one non-model entry in the current snapshot (`"sample_spec"`), so the upstream
schema is not guaranteed to be uniform across all keys. If a future LiteLLM snapshot
changes `gpt-4o` or `claude-3-5-sonnet-20241022`'s value to a non-dict, or those exact keys
are renamed/removed upstream (which already silently no-ops the `if model in data:` guard
today), the workflow either silently skips the spot-check (key renamed) or throws an
unhandled `AttributeError` traceback instead of the intended clean assertion message.
Either way the workflow still fails closed overall (no auto-merge; D-06b requires human
review of the resulting PR regardless), so this is informational rather than a real risk —
a clearer failure mode would just speed up triage when the scheduled job breaks.
**Fix:**
```python
for model in ['gpt-4o', 'claude-3-5-sonnet-20241022']:
    if model in data:
        row = data[model]
        assert isinstance(row, dict), f'{model} entry is not an object: {type(row).__name__}'
        cost = row.get('input_cost_per_token', 0)
        assert 0 < cost < 0.01, f'Implausible input cost for {model}: {cost}'
```

### IN-02: `EngineModels` role resolution treats an explicit empty string the same as "unset"

**File:** `src/prevue/config.py:278-282`
**Issue:** `_resolve_engine_models._role()` uses `if val:` to decide whether
`models.<role>` overrides `engine.model`. A consumer who writes
`engine.models.classify: ""` in `prevue.yml` (e.g. attempting to explicitly force the bare
engine default for one role) gets silently overridden back to `engine.model` instead, with
no warning. This matches the existing falsy-check idiom used elsewhere in the same module
(`_resolve_model`, `_resolve_engine`), so it is consistent project style rather than an
isolated mistake, and the practical impact is low since an empty model string is a YAML
authoring mistake either way. Noting for awareness only — not required for this phase.
**Fix:** Optional — if explicit "no override" support is ever wanted, distinguish `None`
(YAML key absent) from `""` (YAML key present but empty) using `role in models_block`
instead of truthiness on `models_block.get(role)`, or add a config-level validation error
for an empty string model name.

---

_Reviewed: 2026-06-30T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
