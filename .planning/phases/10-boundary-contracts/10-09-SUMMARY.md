---
phase: 10-boundary-contracts
plan: "09"
subsystem: engines
tags: [copilot-cli, otel, usage-capture, perf-03, gap-closure]

# Dependency graph
requires:
  - phase: 10-08
    provides: copilot-cli usage_capture="none" honest-estimate precedent (now superseded)
provides:
  - "usage.py::_parse_copilot_otel correctly parses the real Copilot CLI file-exporter JSONL schema (flat per-line {\"type\": \"span\"|\"metric\", \"attributes\": {...}} records with gen_ai.usage.* keys)"
  - copilot-cli's CliEngineSpec.usage_capture restored to "otel-jsonl" with an accurate root-cause comment
  - COPILOT_OTEL_FILE_EXPORTER_PATH wired into both prevue-review.yml and prevue-command-run.yml as a per-invocation runner.temp path
affects: [phase-11-skills-as-pinned-external-repo, phase-12-cross-file-dependency-context]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Copilot CLI OTEL file exporter writes flat per-line JSON records (type/attributes-as-dict), not nested OTLP resourceSpans->scopeSpans->spans — verify vendor telemetry schemas against a real local CLI install, not assumed OTLP-spec conformance"
    - "type != \"span\" records (e.g. \"metric\") must be filtered before field extraction, not just malformed-shape-checked, when a telemetry stream mixes record kinds on one line-delimited channel"

key-files:
  created: []
  modified:
    - src/prevue/engines/usage.py
    - src/prevue/engines/spec.py
    - src/prevue/engines/cli_adapter.py
    - .github/workflows/prevue-review.yml
    - .github/workflows/prevue-command-run.yml
    - tests/test_usage_capture.py
    - tests/test_reusable_workflow_yaml.py
    - tests/fixtures/usage/copilot_otel.jsonl
    - docs/configuration.md

key-decisions:
  - "_parse_copilot_otel rewritten for the real flat span-per-line schema (gen_ai.usage.* keys, attributes as a plain dict) instead of the fictitious nested resourceSpans->scopeSpans->spans OTLP shape the real exporter never produces — root-caused against a local gh copilot v1.0.67 install"
  - "cache_creation added as a new field on _parse_copilot_otel's return dict (additive, not breaking) — flow._pick_real_token_fields already reads captured.get(\"cache_creation\") generically, so no change needed there"
  - "github.copilot.cost OTEL attribute intentionally NOT read into the parser's output — cost stays derived only via the existing pricing.compute_cost seam from token counts, keeping one auditable cost-computation path (T-10-09-02)"
  - "copilot-cli usage_capture flipped back from \"none\" to \"otel-jsonl\", reversing the 10-08 gap-closure flip whose \"no CI-viable OTEL export\" conclusion is now known to be stale"
  - "COPILOT_OTEL_FILE_EXPORTER_PATH set unconditionally (not per-engine-gated) in both workflow YAML env blocks — inert for non-Copilot engines since their specs never read the var, simpler than a conditional expression"
  - "Live-CI spot-check (real COPILOT_GITHUB_TOKEN, real sandbox PR, confirming estimated=False end-to-end) is explicitly left open — this plan proves the parser is schema-correct against real fixture data and wires the env var, but cannot exercise the actual Copilot CLI subprocess from this environment"

patterns-established:
  - "When a prior gap-closure plan's root-cause conclusion is later found stale, the superseding plan's comment must state the supersession explicitly (date + what changed) rather than silently overwriting history — makes the audit trail legible in code, not just in STATE.md"

requirements-completed: [PERF-03]

# Metrics
duration: 12min
completed: 2026-07-01
---

# Phase 10 Plan 09: Copilot OTEL Real-Schema Parser Fix Summary

**Rewrote `_parse_copilot_otel` for the real flat per-line Copilot CLI OTEL JSONL schema (`gen_ai.usage.*` keys, attributes as a plain dict) instead of a fictitious nested OTLP shape, then flipped `copilot-cli` back to `usage_capture="otel-jsonl"` and wired `COPILOT_OTEL_FILE_EXPORTER_PATH` into both reusable workflows — closing the last `human_needed` gap from `10-VERIFICATION.md`.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-01T18:31:00Z
- **Completed:** 2026-07-01T18:43:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- `_parse_copilot_otel` fully rewritten to walk flat per-line `{"type": "span"|"metric", "attributes": {...}}` records instead of the never-produced nested `resourceSpans -> scopeSpans -> spans` OTLP shape, matching the real `gh copilot` v1.0.67 file exporter output verified locally
- New `"cache_creation"` field added to the parser's return dict (additive, consumed automatically by `flow._pick_real_token_fields`)
- `_extract_attr_value` and the old `llm.usage.*`-style OTLP constants deleted; replaced with flat `gen_ai.usage.*` module constants
- `tests/fixtures/usage/copilot_otel.jsonl` and `tests/test_usage_capture.py`'s Copilot OTEL test group rewritten/extended for the real schema, including new tests for `cache_creation` summing, metric-type-record skipping, and malformed/missing `attributes` handling
- `copilot-cli`'s `CliEngineSpec.usage_capture` restored to `"otel-jsonl"` with a comment explicitly stating the 10-08 "no CI-viable OTEL" conclusion is superseded and citing the real root cause
- `COPILOT_OTEL_FILE_EXPORTER_PATH: ${{ runner.temp }}/copilot-otel` wired into both `prevue-review.yml`'s "Run review" step and `prevue-command-run.yml`'s "Prevue command" step
- `docs/configuration.md` updated with a paragraph describing Copilot's real OTEL-based token capture path and its bytes/4 estimate fallback
- Stale comments in `cli_adapter.py` and `test_reusable_workflow_yaml.py` that described the now-superseded `usage_capture="none"` state corrected (Rule 1)

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite `_parse_copilot_otel` for the real flat-span JSONL schema (TDD)** - `2a75168` (fix)
2. **Task 2: Flip `copilot-cli` back to `usage_capture="otel-jsonl"` and wire `COPILOT_OTEL_FILE_EXPORTER_PATH` into both workflows** - `60daa3e` (feat)

**Deviation fix (Rule 1):** `7c3d17e` (fix) — corrected stale `usage_capture="none"` comments in `cli_adapter.py` and `test_reusable_workflow_yaml.py` left inconsistent by Task 2's spec flip.

## Files Created/Modified
- `src/prevue/engines/usage.py` - `_parse_copilot_otel` rewritten for the flat span-per-line schema; new `_OTEL_INPUT_TOKENS`/`_OTEL_OUTPUT_TOKENS`/`_OTEL_CACHE_READ_TOKENS`/`_OTEL_CACHE_CREATION_TOKENS` constants replace the old OTLP-style ones; `_extract_attr_value` deleted; docstrings updated to cite the local `gh copilot` v1.0.67 verification
- `src/prevue/engines/spec.py` - `copilot-cli`'s `usage_capture` field changed `"none"` -> `"otel-jsonl"`; comment block rewritten to describe the supersession and note the open live-CI spot-check follow-up
- `src/prevue/engines/cli_adapter.py` - stale `review()` docstring comment corrected to describe the restored `otel-jsonl` path (Rule 1)
- `.github/workflows/prevue-review.yml` - `COPILOT_OTEL_FILE_EXPORTER_PATH: ${{ runner.temp }}/copilot-otel` added to the "Run review" step env block
- `.github/workflows/prevue-command-run.yml` - identical `COPILOT_OTEL_FILE_EXPORTER_PATH` line added to the "Prevue command" step env block, for parity
- `tests/test_usage_capture.py` - Copilot OTEL test group rewritten for the flat schema; new tests `test_copilot_otel_cache_creation_tokens`, `test_copilot_otel_ignores_metric_type_records`, `test_copilot_otel_malformed_attributes_dict_skipped`, `test_copilot_otel_missing_attributes_key_skipped`
- `tests/test_reusable_workflow_yaml.py` - stale OUTP-05 section-header comment corrected (Rule 1); `test_otel_env_end_to_end_capture` continues to pass unchanged against the rewritten fixture
- `tests/fixtures/usage/copilot_otel.jsonl` - rewritten to the flat span-per-line shape, preserving the same summed token totals (input=2100, output=300, cache_read=1050) so only the JSON shape changed, not the expected numbers
- `docs/configuration.md` - new paragraph after the "Available engines" table describing Copilot's real OTEL-based token capture path and its `~est` bytes/4 fallback

## Decisions Made
- **Root cause was a schema mismatch, not a missing feature**: the 10-08 gap-closure plan concluded OTEL export "has no effect" on Copilot CLI based on the pinned `@github/copilot@1.0.61`. A local install of the real CLI (`gh copilot` v1.0.67) during this plan's investigation confirmed OTEL export is real and documented (`copilot help monitoring`) — the parser was simply reading the wrong (fictitious, non-OTLP) nested shape, so `span_count` never incremented and the parser always returned `None`, masking a working exporter behind a parser bug.
- **`cache_creation` is additive, not a breaking change**: `flow._pick_real_token_fields` already iterates `("input", "output", "cache_read", "cache_creation", "cost_usd")` generically via `captured.get(key)`, so adding the field to `_parse_copilot_otel`'s return dict required zero changes to `flow.py`.
- **Cost stays derived from tokens, never read from OTEL attributes directly**: `github.copilot.cost` is present in real span attributes but intentionally not consumed by the parser — keeping the single `pricing.compute_cost` seam as the only cost-computation path avoids two potentially-inconsistent dollar figures (T-10-09-02 in the threat model).
- **`COPILOT_OTEL_FILE_EXPORTER_PATH` set unconditionally in both workflows**: unlike per-engine secrets (`COPILOT_GITHUB_TOKEN` etc.), this path is inert for non-Copilot engines because `flow.py`'s OTEL path resolution is already gated on `spec.usage_capture == "otel-jsonl"` — no need for a per-engine conditional expression.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected stale `usage_capture="none"` comments left inconsistent by Task 2's spec flip**
- **Found during:** Task 2 (flipping `copilot-cli` back to `otel-jsonl`)
- **Issue:** `cli_adapter.py`'s `review()` method had a comment describing `copilot-cli` as using `usage_capture="none"` with "no CI-viable OTEL enablement mechanism" (written for 10-08). `test_reusable_workflow_yaml.py` had a section-header comment above `test_job_outputs_map_declared` making the same now-false claim. Neither file was in the plan's explicit `files_modified` list, but both directly and unavoidably went stale the moment `spec.py`'s `usage_capture` field changed, and would mislead a future reader into thinking Copilot still uses the estimate-only path.
- **Fix:** Rewrote both comments to state the restored `otel-jsonl` path and cite this plan (10-09) as the supersession of 10-08's conclusion.
- **Files modified:** `src/prevue/engines/cli_adapter.py`, `tests/test_reusable_workflow_yaml.py`
- **Verification:** Full test suite (`uv run pytest -q`, 822 passed) + `ruff check`/`ruff format --check` clean after the fix; no test asserted on the prior comment wording.
- **Committed in:** `7c3d17e`

---

**Total deviations:** 1 auto-fixed (1 bug — stale comments)
**Impact on plan:** Documentation-accuracy only; no behavior change beyond what Task 2 already specified. No scope creep.

## Issues Encountered
None. `_parse_copilot_otel`'s test suite went straight to GREEN once the rewrite matched the plan's specified schema — no iteration needed on the parser logic itself.

## User Setup Required
None — no new consumer-facing configuration is introduced. `COPILOT_OTEL_FILE_EXPORTER_PATH` is set automatically by the reusable workflow; consumers using `copilot-cli` need no action to benefit from real token capture once this plan's changes reach `main`.

## Next Phase Readiness
- All automated acceptance criteria from `10-09-PLAN.md` are met: `_parse_copilot_otel` matches the real flat-span schema with zero remaining references to the fictitious nested OTLP shape; `copilot-cli`'s spec reports `usage_capture="otel-jsonl"`; both reusable workflow YAML files wire `COPILOT_OTEL_FILE_EXPORTER_PATH`; the full test suite (822 tests) and `scripts/ci-local.sh` (pytest + ruff + actionlint + zizmor) are green.
- **Explicitly NOT closed by this plan**, per the plan's own framing: a live CI spot-check on a real sandbox PR with a real `COPILOT_GITHUB_TOKEN` confirming the sticky Tokens line shows `estimated=False` (no `~est` label) end-to-end. Local unit tests and the fixture-driven parser rewrite prove the parser is now schema-correct against the real flat-span format, but only an actual GitHub Actions run with the real Copilot CLI subprocess writing real OTEL spans can confirm the full wiring (workflow env -> CLI subprocess -> file write -> parser read) works end-to-end in production. This remains an open `human_verification` follow-up.
- Phase 10 (boundary-contracts) has no other known `human_needed` gaps from `10-VERIFICATION.md` after this plan; the orchestrator should confirm phase-completion status against the updated `10-VERIFICATION.md` before transitioning.

---
*Phase: 10-boundary-contracts*
*Completed: 2026-07-01*

## Self-Check: PASSED

All 9 claimed files verified present on disk; all 3 claimed commit hashes (`2a75168`, `60daa3e`, `7c3d17e`) verified present in git log.
