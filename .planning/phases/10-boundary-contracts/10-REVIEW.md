---
phase: 10-boundary-contracts
reviewed: 2026-07-01T13:33:51Z
depth: standard
files_reviewed: 34
files_reviewed_list:
  - .github/scripts/install-engine-cli.sh
  - .github/workflows/prevue-command-run.yml
  - .github/workflows/prevue-review.yml
  - .github/workflows/review.yml
  - .github/workflows/update-pricing.yml
  - docs/configuration.md
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
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-07-01T13:33:51Z
**Depth:** standard
**Files Reviewed:** 34
**Status:** issues_found

## Summary

This is a re-review of phase 10 (boundary contracts) against the current tree, after the
prior `10-REVIEW.md` / `10-REVIEW-FIX.md` iteration (CR-01 pricing-shape validator, WR-01
docs, WR-02 command-run secret wiring, WR-03 antigravity install exclusion). All four fixes
from that iteration were verified correct in isolation: `EngineConfig.pricing` now has a
`_validate_pricing` field validator that raises `ValidationError` on a non-dict `pricing`
value or a non-dict/non-null row (confirmed by direct construction), `docs/configuration.md`
now documents `engine.models`/`engine.raw_args`/`engine.pricing`, `prevue-command-run.yml`
now wires `ANTIGRAVITY_API_KEY`/`GEMINI_API_KEY` into the `Prevue command` step, and
`prevue-review.yml`'s "Install engine CLI" step now excludes `antigravity-cli`. The full
in-scope pytest suite (807 tests) passes.

This pass found that the WR-03 fix was applied to only one of the two workflow entry points
that run the "Install engine CLI" step — `prevue-command-run.yml` has its own separate
install step that still runs unconditionally for `antigravity-cli`, reproducing the exact
waste/attack-surface issue WR-03 was meant to close, and reproducing the exact
two-entry-points-drift failure mode that WR-02 (from the same review iteration) was meant to
close. Additionally, the CR-01 pricing validator fix shipped with zero regression test
coverage — no test asserts `EngineConfig.model_validate` actually rejects a malformed
`engine.pricing` value, so a future refactor could silently regress it without any test
failing. The remaining prior INFO findings (IN-01 defense-in-depth guard in
`_lookup_row`/`compute_cost`, IN-02 placeholder summary fallback, IN-03 docstring/behavior
mismatch) are unchanged and confirmed still present — they were explicitly out of scope for
the prior fix pass (`fix_scope: critical_warning`) and remain accurately documented as such.

## Structural Findings (fallow)

None provided for this review invocation.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: `prevue-command-run.yml`'s "Install engine CLI" step still runs for `antigravity-cli`, reproducing the issue WR-03 fixed only in `prevue-review.yml`

**File:** `.github/workflows/prevue-command-run.yml:57-61`, `.github/workflows/prevue-review.yml:157-167`

**Issue:** The prior review's WR-03 finding ("Install engine CLI runs for antigravity-cli even
though the engine is registered non-functional") was fixed by adding
`inputs.engine != 'antigravity-cli'` to the `if:` condition of `prevue-review.yml`'s "Install
engine CLI" step (line 164, with an explanatory comment referencing WR-03). But
`prevue-command-run.yml` — the `/prevue` slash-command dispatch entry point into the exact
same review pipeline — has its own, separate "Install engine CLI" step:

```yaml
- name: Install engine CLI
  if: github.event.client_payload.needs_engine
  env:
    PREVUE_ENGINE: ${{ github.event.client_payload.engine }}
  run: bash .prevue/.github/scripts/install-engine-cli.sh
```

This condition was never updated to exclude `antigravity-cli`. A `/prevue review` command
dispatched with `engine: antigravity-cli` (and `needs_engine: true`) still runs the full
`curl` + optional-checksum + `bash "$installer"` third-party install
(`.github/scripts/install-engine-cli.sh`'s `antigravity-cli)` case) before
`require_functional_adapter` rejects the engine downstream in `review.py` — exactly the
wasted install/attack-surface spend WR-03 was written to close, now present in one of the two
entry points but not the other.

This is also a second, fresh instance of the class of bug the *same review iteration's*
WR-02 finding described ("a `/prevue` command-dispatch workflow ... missing ... wiring
present in the primary reusable workflow ... a real drift between the two entry points into
the same review pipeline") — WR-02 was fixed for secret wiring, but the parallel install-step
gating fix (WR-03) was not mirrored to the second entry point at the same time, so the two
workflows have drifted again on a different axis.

No test guards this: `tests/test_reusable_workflow_yaml.py` only loads and asserts against
`prevue-review.yml` (`REUSABLE_WORKFLOW` constant, line 10-12); `prevue-command-run.yml` has
no equivalent test file, so this class of two-workflow drift has no regression coverage at
all in either direction.

**Fix:** Add the same `&& github.event.client_payload.engine != 'antigravity-cli'` exclusion
to `prevue-command-run.yml`'s "Install engine CLI" step `if:` condition, mirroring
`prevue-review.yml:164`:

```yaml
- name: Install engine CLI
  if: >-
    github.event.client_payload.needs_engine &&
    github.event.client_payload.engine != 'antigravity-cli'
  env:
    PREVUE_ENGINE: ${{ github.event.client_payload.engine }}
  run: bash .prevue/.github/scripts/install-engine-cli.sh
```

Consider also adding a shared regression test (or extending
`test_reusable_workflow_yaml.py` to parametrize over both workflow files) that asserts both
"Install engine CLI" steps exclude any engine with `functional=False` in `CLI_ENGINE_SPECS`,
so this drift cannot silently reappear a third time as new non-functional engines are added.

### WR-02: The `_validate_pricing` field validator (CR-01 fix) has no regression test coverage

**File:** `src/prevue/config.py:160-184`, `tests/test_pricing.py`, `tests/test_raw_args.py`

**Issue:** The prior review's CR-01 finding was fixed by adding a
`field_validator("pricing", mode="before")` on `EngineConfig` that rejects a non-dict
`pricing` value or a non-dict/non-null row within it. This validator is exercised manually
here and confirmed to work correctly:

```
>>> EngineConfig.model_validate({"pricing": {"gpt-4o": "not-a-dict"}})
pydantic.ValidationError: ... engine.pricing['gpt-4o'] must be a mapping or null ...
```

But no test in the repository calls it. `tests/test_pricing.py` only tests the pure
`compute_cost`/`load_pricing_table` functions with hand-built `override`/`table` dicts — it
never constructs an `EngineConfig` and never imports `_validate_pricing`. The sibling
`raw_args` validator (`_validate_raw_args`), by contrast, has a full dedicated test file
(`tests/test_raw_args.py`, 124 lines) covering the string-rejection, non-list-rejection,
non-string-element-rejection, and `None`-tolerance cases. `_validate_pricing` mirrors that
validator's logic and intent but has zero equivalent coverage — a future refactor of
`EngineConfig` (e.g. accidentally dropping the `mode="before"` validator during a Pydantic
version bump, or a copy-paste edit that loosens the `isinstance` check) would not be caught
by any test, silently reopening the exact crash this phase's own review cycle flagged as
CRITICAL.

**Fix:** Add a `tests/test_pricing.py` (or new `test_engine_config_pricing.py`) section
mirroring `test_raw_args.py`'s structure, e.g.:

```python
import pytest
from pydantic import ValidationError
from prevue.config import EngineConfig

def test_pricing_rejects_non_dict_value():
    with pytest.raises(ValidationError, match="mapping"):
        EngineConfig.model_validate({"pricing": "not-a-dict"})

def test_pricing_rejects_non_dict_row():
    with pytest.raises(ValidationError, match="mapping or null"):
        EngineConfig.model_validate({"pricing": {"gpt-4o": "not-a-dict"}})

def test_pricing_accepts_none():
    cfg = EngineConfig.model_validate({"pricing": None})
    assert cfg.pricing is None

def test_pricing_accepts_valid_row():
    cfg = EngineConfig.model_validate(
        {"pricing": {"gpt-4o": {"input_cost_per_token": 1e-6}}}
    )
    assert cfg.pricing == {"gpt-4o": {"input_cost_per_token": 1e-6}}
```

## Info

### IN-01: `_lookup_row`/`compute_cost` still has no defense-in-depth guard against non-dict pricing rows (carried forward, unfixed — correctly out of scope)

**File:** `src/prevue/pricing/__init__.py:105-141, 187-201`

**Issue:** Unchanged from the prior review. `_lookup_row` and `compute_cost` still assume
every value under `override`/`table` is a dict (`row.get(...)`) with no `isinstance` guard.
The Pydantic-boundary fix (CR-01/`_validate_pricing`) closes the `prevue.yml`-sourced attack
surface, but `compute_cost` remains a public function; called directly (as in
`update-pricing.yml`'s validation step, or any future test/caller) with a malformed
`override`/`table` dict built outside `EngineConfig`, it still crashes uncaught:

```
>>> compute_cost("openai", "gpt-4o", {"input": 100, "output": 10},
...              override={"gpt-4o": "not-a-dict"}, table={})
AttributeError: 'str' object has no attribute 'get'
```

Confirmed still reproducible against the current code. This is intentionally unaddressed —
the prior fix report explicitly scoped it out (`fix_scope: critical_warning`, IN-01 deferred
to a future `--all` pass) — carried forward here for visibility, not as a new finding.

**Fix:** (unchanged from prior review) Add `isinstance(row, dict)` guards in `_lookup_row`'s
lookup branches (override exact/normalized, table exact/normalized, suffix-fallback) so a
malformed row degrades to "skip this entry" rather than crashing, matching the defensive
style already used in `usage.py`'s OTEL parsing.

### IN-02: `combined_summary` in `review.py` still falls back to a bare, unlabeled placeholder heading (carried forward, unfixed — correctly out of scope)

**File:** `src/prevue/review.py:1168`

**Issue:** Unchanged from the prior review.
`combined_summary = "\n\n".join(s for s in all_summaries if s) or "## Review\n"` still
renders a bare, unlabeled `## Review` heading when every call result's `summary_markdown` is
falsy, with no signal to the reader that this is a fallback rather than genuine (if terse)
prose. Confirmed still present at the same line. Intentionally unaddressed per the prior fix
report's scoping.

**Fix:** (unchanged from prior review) Use a more descriptive fallback, e.g.
`"_No review summary was returned by the engine._"`.

### IN-03: `config.py` module docstring's fallback-model precedence still contradicts `review.py`'s actual behavior (carried forward, unfixed — correctly out of scope)

**File:** `src/prevue/config.py:9-14`, `src/prevue/review.py:659,780,850`

**Issue:** Unchanged from the prior review. The module docstring's precedence knob 3 still
reads `(no env override) > classification.fallback.model in yml > None`, while
`review.py`'s `_effective_classify_model` (line 659) and `_skill_select_model` (line 780)
both end with `or os.environ.get("PREVUE_MODEL", os.environ.get("COPILOT_MODEL"))` — an env
override applied last, directly contradicting the docstring's "(no env override)"
parenthetical. Confirmed still present at the same lines. Intentionally unaddressed per the
prior fix report's scoping.

**Fix:** (unchanged from prior review) Update the `config.py` docstring's knob-3 line to:
`3. fallback model: PREVUE_MODEL/COPILOT_MODEL env (applied at the review.py call site) >
classification.fallback.model in yml > None`.

---

_Reviewed: 2026-07-01T13:33:51Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
