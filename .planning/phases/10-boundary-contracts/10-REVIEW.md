---
phase: 10-boundary-contracts
reviewed: 2026-07-01T00:00:00Z
depth: standard
files_reviewed: 37
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
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-07-01T00:00:00Z
**Depth:** standard
**Files Reviewed:** 37
**Status:** issues_found

## Summary

This is a fresh pass over the current state of phase 10 (boundary contracts) — the config
precedence ladder (`EngineConfig`: raw_args, per-role models, pricing override), the new
spec-driven `CliEngineAdapter` that replaced the four per-engine adapter modules, the usage-capture
/ pricing / cost pipeline, the reusable-workflow YAML contract, and the sticky-comment renderer.
The `claude-code-oauth-token` documentation drift flagged in an earlier review iteration of this
phase has since been fixed — `docs/configuration.md` now correctly documents
`CLAUDE_CODE_OAUTH_TOKEN` throughout. The architecture (one generic adapter parameterized by a
declarative `CliEngineSpec`, instead of four near-duplicate adapter classes) is sound, and the
`script -qec` pseudo-TTY wrapper for Antigravity was traced end-to-end and confirmed to deliver
the prompt via an environment variable (never shell-interpolated), so no command-injection risk
exists there despite building a shell command string.

The most serious findings this pass are two config-loading crash paths: `load_config()` is called
in `run_review()` with **no exception handling**, while a sibling code path (consumer skill
loading, ~190 lines later in the same function) explicitly catches `ValidationError` and fails
closed with a structured check run instead of crashing. Two distinct, entirely plausible consumer
YAML typos (`engine.models:` or `engine.raw_args:` left with an empty block, which YAML parses to
`None`) raise an uncaught `pydantic.ValidationError` that propagates out of `run_review()` with no
`prevue/review` check published and no sticky comment — a silent, undiagnosable job crash that
directly contradicts the fail-closed design used everywhere else in this same function. A further
finding shows the vendored pricing table's key format does not match plain Anthropic model
strings, silently defeating the `update-pricing.yml` spot-check for the exact model name used
throughout the docs and tests.

## Critical Issues

### CR-01: `load_config()` crashes the review job on a trivial consumer YAML typo

**File:** `src/prevue/review.py:500`
**Issue:** `run_review()` calls `config = load_config(str(consumer_path))` with no exception
handling. `load_config` builds `EngineConfig.model_validate(engine_block)`
(`_build_engine_config`, `src/prevue/config.py:334-339`), and `EngineConfig.models` is typed as
`EngineModels` (no `| None`, no custom validator tolerating `None`). A completely ordinary
consumer YAML typo — writing:
```yaml
engine:
  name: copilot-cli
  models:
```
with nothing indented underneath (valid YAML; parses to `{"models": None}`) — raises an uncaught
`pydantic.ValidationError` that propagates out of `load_config()`, out of `run_review()`, and
crashes the whole job. Verified directly against the current code:
```
>>> EngineConfig.model_validate({"name": "x", "models": None})
ValidationError: models — Input should be a valid dictionary or instance of EngineModels
```
This directly contradicts the framework's own fail-closed design: the sibling consumer-skill-load
call a few dozen lines later (`src/prevue/review.py:690-716`) explicitly wraps its fallible call
in `except (ValidationError, OSError, UnicodeDecodeError, yaml.YAMLError)` and publishes a
structured failure check instead of crashing:
```python
except (ValidationError, OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
    print(f"prevue: consumer skill load failed: {exc!r}", file=sys.stderr)
    reason = (...)
    _publish_skip(pr, ctx, diff.head_sha, reason=reason, conclusion="failure", title="review failed")
    return
```
`load_config()` — the very first fallible, consumer-controlled operation in `run_review()` — gets
no equivalent protection, even though `ValidationError` from a malformed `prevue.yml` is entirely
foreseeable (it's precisely why `skip.skip_title_patterns`, `EngineConfig.raw_args`, and every
other Pydantic field in this module validates and raises on purpose).
**Fix:**
```python
consumer_path = resolve_consumer_config_path(
    os.environ.get("PREVUE_CONFIG_PATH"),
    consumer_root=os.environ.get("PREVUE_CONSUMER_ROOT"),
)
try:
    config = load_config(str(consumer_path))
except ValidationError as exc:
    print(f"prevue: invalid prevue.yml config: {exc!r}", file=sys.stderr)
    pr = get_authenticated_pull(ctx)  # needed for _publish_skip
    _publish_skip(
        pr, ctx, pr.head.sha,
        reason=f"Invalid `prevue.yml` configuration ({type(exc).__name__}). See workflow logs.",
        conclusion="failure",
        title="review failed",
    )
    return
```
(`pr = get_authenticated_pull(ctx)` currently runs *after* `load_config()` in the unmodified flow;
the fix must either move the pull fetch earlier or publish the failure via the checks API directly
without a `pr` object.)

### CR-02: `engine.raw_args:` left empty in YAML crashes `load_config()` the same way

**File:** `src/prevue/config.py:126-152`, `src/prevue/review.py:500`
**Issue:** Same failure class as CR-01, different field. `EngineConfig._validate_raw_args`
(`mode="before"`) explicitly rejects any non-list value, including `None`:
```
>>> EngineConfig.model_validate({"name": "x", "raw_args": None})
ValidationError: raw_args — Value error, engine.raw_args must be a list of strings, got 'NoneType': None
```
Writing `engine:\n  raw_args:\n` (again, ordinary/plausible YAML — e.g. a consumer templating
values in CI, or copy-pasting a docs example and deleting the list items) parses to
`{"raw_args": None}` and raises the same uncaught `ValidationError` through the same unprotected
`load_config()` call site as CR-01. Both findings share one root cause (no exception boundary
around `load_config()`) and one fix location.
**Fix:** Apply the same try/except from CR-01 around `load_config()` (fixes both CR-01 and CR-02
simultaneously since both are `ValidationError` subtypes at the same call site). As defense in
depth, also make the validator explicitly tolerate `None`:
```python
@field_validator("raw_args", mode="before")
@classmethod
def _validate_raw_args(cls, value: object) -> list[str]:
    if value is None:
        return []
    ...
```
Note this addition alone does not fix CR-01 (the `models` field has no equivalent validator), so
the `load_config()` try/except is required regardless.

## Warnings

### WR-01: Vendored pricing table has no plain-key entry for Claude models — `compute_cost` silently returns `None`

**File:** `src/prevue/pricing/model_prices.json`, `src/prevue/pricing/__init__.py:64-79`,
`.github/workflows/update-pricing.yml:33-47`
**Issue:** The currently-vendored snapshot (2918 entries) has **no** `claude-3-5-sonnet-20241022`
key — verified directly (`'claude-3-5-sonnet-20241022' in data` is `False`). Only
provider-prefixed variants exist (`anthropic.claude-3-5-sonnet-20241022-v2:0`,
`bedrock/invoke/anthropic.claude-3-5-sonnet-20240620-v1:0`, region-prefixed forms like
`eu.anthropic....`, etc.), using a `.` separator and `bedrock/invoke/`/region prefixes that
`_normalize_model()` does not know how to strip (it only strips `anthropic/`, `openai/`,
`google/`, `vertex_ai/`, `azure/`, `bedrock/` as slash-suffixed prefixes). Two consequences:
1. `update-pricing.yml`'s "Validate downloaded pricing JSON" spot-check uses
   `if model in data: assert 0 < cost < 0.01` — since the key is simply absent, the `if` is never
   entered and the assertion never runs. The spot-check has therefore never actually verified
   Claude pricing in this snapshot; it silently degrades to a no-op for exactly the model it is
   meant to catch regressions on.
2. `compute_cost("claude-code-cli", "claude-3-5-sonnet-20241022", usage, ...)` against the real
   vendored table (as opposed to the small test fixture, which *does* define this key) returns
   `None` — "unknown model, no cost" — for the exact model name used throughout
   `docs/configuration.md` and the test suite as the canonical example. In production this is
   currently masked for `claude-code-cli` because `compute_cost` prefers `usage["cost_usd"]`
   (Claude's vendor-reported `total_cost_usd`) before ever consulting the table — but the same
   `_normalize_model`/table-lookup path is reused by `flow._estimated_cost_usd` for engines with no
   vendor-reported cost, so any future model-name reuse across engines (or a Claude envelope
   missing `total_cost_usd`) will silently produce no cost with no error surfaced anywhere.
**Fix:** Extend `_normalize_model()` to strip the vendored table's actual prefix conventions
(`anthropic.`, `bedrock/invoke/`, two-letter region prefixes like `eu.`/`apac.`) or add a
suffix-aware fallback lookup, and change the `update-pricing.yml` spot-check from a silent `if` to
an `assert model in data, f"pricing snapshot missing expected model {model}"` so a future snapshot
update that actually removes/renames the key fails loudly instead of silently no-opping.

### WR-02: `docs/configuration.md` Secrets table omits `antigravity-api-key` and `gemini-api-key`

**File:** `docs/configuration.md:273-280`
**Issue:** The reusable workflow (`prevue-review.yml:34-44`) declares five `workflow_call` secrets
(`copilot-github-token`, `claude-code-oauth-token`, `cursor-api-key`, `antigravity-api-key`,
`gemini-api-key`), and `tests/test_reusable_workflow_yaml.py::test_antigravity_secret_in_workflow_call_secrets`
asserts `antigravity-api-key` is present and `required: false`. The docs' "### Secrets" table,
however, lists only three rows (`copilot-github-token`, `claude-code-oauth-token`,
`cursor-api-key`). A consumer wanting to wire up `antigravity-cli` — a documented, registered
engine per the "Available engines" table earlier in the same doc, even though currently
non-functional — has no documented secret name or env-var mapping in the one place (`### Secrets`)
they would look for it; they would need to read the workflow YAML or `cli_adapter.py` directly.
**Fix:** Add the two missing rows, e.g.:
```markdown
| `antigravity-api-key` | No | `antigravity-cli` | API key for `agy` (registered, not yet functional). Maps to `ANTIGRAVITY_API_KEY` |
| `gemini-api-key` | No | `antigravity-cli` | Documented alias for `antigravity-api-key`. Maps to `GEMINI_API_KEY` |
```

### WR-03: `_resolve_model()` is dead code — superseded by `_resolve_engine_models`/`resolve_review_model` but never removed

**File:** `src/prevue/config.py:241-257`
**Issue:** `_resolve_model(raw)` implements a model-precedence ladder (`PREVUE_MODEL` env >
`COPILOT_MODEL` env > `engine.model` yml > `None`), but no production code path calls it — a
search for `_resolve_model(` outside its own definition finds only `tests/test_config_precedence.py`.
Production code resolves models via `_resolve_engine_models()` (per-role: classify/review/
consolidate) plus `resolve_review_model()` (the call-site env-override layer), a materially
different and more capable contract (per-role overrides) that `_resolve_model` has no notion of.
Keeping `_resolve_model` around risks a future maintainer either wiring it back in by mistake, or
mistakenly treating `test_model_precedence_matrix` as documentation of the live model-resolution
behavior when it in fact only documents this superseded, unused function.
**Fix:** Delete `_resolve_model()` and its dedicated test parametrization (or, if it must be kept
for historical/precedent reasons, add an explicit "not on the live call path — see
`_resolve_engine_models`/`resolve_review_model` for the current model precedence contract"
docstring note, matching the style already used for other retained-for-tests shims in this
codebase, e.g. `copilot_cli.py`'s `CopilotCliAdapter` alias).

### WR-04: `raw_args`/`pricing_override` threading silently no-ops when a caller supplies a custom `adapter`

**File:** `src/prevue/review.py:582-598`
**Issue:** The guard `if not adapter and config.engine_config.raw_args and isinstance(engine, CliEngineAdapter):`
(and the analogous pricing-override guard immediately after) means that whenever `run_review()` is
invoked with a non-`None` `adapter=`, the base-ref `prevue.yml`'s `engine.raw_args` and
`engine.pricing` are silently dropped with no diagnostic, even though `config.engine_config` still
carries the loaded values. Today this is masked in production: the only caller that passes
`adapter` is `commands.py::run_command(adapter=...)`, which is itself always invoked with
`adapter=None` from `cli.py:91` (`return run_command()`), so the guard's `not adapter` branch is
always taken in the current call graph. But the gate exists and will silently fire the moment
either call site changes — e.g. a future subcommand or test-harness wiring injects a pre-built
adapter for some legitimate reason — producing a "why did my raw_args/pricing override silently
stop applying" bug with zero log signal to explain it.
**Fix:** Log a stderr notice on the else-branch when the values are present but skipped due to a
custom adapter:
```python
elif adapter and (config.engine_config.raw_args or config.engine_config.pricing is not None):
    print(
        "prevue: custom adapter supplied; engine.raw_args/pricing from prevue.yml not applied",
        file=sys.stderr,
    )
```

## Info

### IN-01: `EngineConfig.raw_args` validator docstring doesn't mention it also rejects `None`

**File:** `src/prevue/config.py:126-152`
**Issue:** Directly related to CR-02: the validator's docstring explains at length *why*
shell-strings and mixed-type lists are rejected (D-10 command-injection guard), but never mentions
that `None` — the actual value produced by an empty `raw_args:` YAML block, and the actual trigger
for CR-02 — is also rejected. A reader auditing "what inputs does this validator reject" would
reasonably assume only shell-strings and non-string list elements are in scope.
**Fix:** Add one line to the docstring, e.g.: "Also rejects `None` (an empty `raw_args:` YAML
block parses to `None`, not `[]`) — this currently crashes `load_config()` uncaught; see the
phase-10 review CR-02 finding for the fix."

### IN-02: `config.py` module docstring's fallback-model precedence contradicts `review.py`'s actual behavior

**File:** `src/prevue/config.py:9-14`, `src/prevue/review.py:622-627,744-748`
**Issue:** The `config.py` module docstring states the precedence ladder's third knob as:
`3. fallback model: (no env override) > classification.fallback.model in yml > None`. But
`review.py`'s actual classify-model and skill-select-model resolution
(`_effective_classify_model`, `_skill_select_model`) both end with
`or os.environ.get("PREVUE_MODEL", os.environ.get("COPILOT_MODEL"))` — i.e. there is an env
override, applied last, directly contradicting the docstring's explicit "(no env override)"
parenthetical. This is a deliberate, intentional deviation documented at the call site itself
("env applied last — matches skill-select path at `_skill_select_model` below"), but the
module-level docstring in `config.py` — the canonical machine-readable precedence reference this
codebase leans on (`CONFIG_PRECEDENCE` constant, grep-tested) — was never updated to match, so the
two docs now disagree on a load-bearing precedence claim for anyone auditing config resolution
from `config.py` alone.
**Fix:** Update the `config.py` docstring's knob-3 line to: `3. fallback model:
PREVUE_MODEL/COPILOT_MODEL env (applied at the review.py call site) > classification.fallback.model
in yml > None`.

---

_Reviewed: 2026-07-01T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
