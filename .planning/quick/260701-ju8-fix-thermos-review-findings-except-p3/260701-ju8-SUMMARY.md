---
phase: quick-260701-ju8
plan: fix-thermos-review-findings-except-p3
subsystem: review-engine
tags: [review-pipeline, engine-adapters, config-resolution, refactor, ci]

# Dependency graph
requires:
  - phase: 10-boundary-contracts
    provides: adapter/config typed boundaries, per-role model resolution, engine spec table
provides:
  - 12 P0/P1/P2 Thermos review findings fixed (T-01 through T-12)
  - review.py split into review_config.py/review_classify.py/review_publish.py
  - flow.py review_with_retry() de-duplicated via InvocationResult/_run_invocation/_merge_retry_tokens
  - four backward-compat shim adapter files deleted
affects: [11-skills-external-repo, 12-cross-file-dependency-context, 13-finding-signal-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-attribute lazy lookup (`import prevue.review as review; review.X(...)`) preserves unittest.mock.patch(\"prevue.review.X\", ...) targets when logic moves to a sibling module without moving the actual patched call site"
    - "CliEngineSpec.secret_env_aliases: tuple[str, ...] for declarative env-var alias fallback instead of name== string checks"
    - "Adapter construction-time kwargs (raw_args, pricing_override) replace post-construction setter mutation"

key-files:
  created:
    - src/prevue/review_config.py
    - src/prevue/review_classify.py
    - src/prevue/review_publish.py
  modified:
    - src/prevue/review.py
    - src/prevue/cli.py
    - src/prevue/config.py
    - src/prevue/engines/registry.py
    - src/prevue/engines/cli_adapter.py
    - src/prevue/engines/base.py
    - src/prevue/engines/flow.py
    - src/prevue/engines/usage.py
    - src/prevue/engines/spec.py
    - src/prevue/output.py
    - src/prevue/classify/llm_fallback.py
    - .github/workflows/prevue-review.yml
    - .github/workflows/prevue-command-run.yml
    - docs/consumer-setup.md
    - docs/GETTING-STARTED.md
    - docs/ARCHITECTURE.md
    - docs/DEVELOPMENT.md
    - tests/test_review_flow.py
    - tests/test_config_precedence.py
    - tests/test_copilot_adapter.py
    - tests/test_cli.py

key-decisions:
  - "T-03: UnknownEngineError now caught alongside NonFunctionalEngineError in run_review's adapter-resolution try/except, degrading to a graceful failure-conclusion skip instead of propagating uncaught"
  - "T-04: emit_machine_output runs before the check-publish RuntimeError raise, so real result/tokens/findings are never lost behind a synthetic failure summary"
  - "T-05 split constrained by test-suite patch targets: all functions/names that tests patch as `prevue.review.X` (load_config, classify, llm_classify, require_functional_adapter, upsert_sticky, conclude_review_check, conclude_skip_check, post_inline_review, fetch_diff(_in_scope), get_authenticated_pull, get_repo, decide_scope, derive_prior_findings, resolve_outdated_prior_findings, read_newest_trusted_sticky_body, upsert_skip_note, emit_machine_output, _upsert_sticky_with_retry) stay physically called from review.py; review_publish.py reaches back into review.py's module namespace via `import prevue.review as review; review.X(...)` for the ones it needs, since a static `from prevue.review import X` would silently stop responding to those patches"
  - "T-07: CliEngineAdapter raw_args/pricing_override are constructor-only; require_functional_adapter/get_adapter accept them as factory kwargs; set_raw_args/set_pricing_override deleted"
  - "T-09a: EngineAdapter.classify_with_tokens() gets a universal base-class default (delegates to classify(), returns (labels, None)); llm_fallback._classify_batch drops its hasattr duck-typing branch"
  - "T-10: antigravity-cli's GEMINI_API_KEY alias is declarative CliEngineSpec.secret_env_aliases data, not a spec.name== string check in cli_adapter._build_env"

requirements-completed: []

# Metrics
duration: ~120min
completed: 2026-07-01
---

# Quick Task 260701-ju8: Fix Phase 10 Thermos review findings (P0/P1/P2) Summary

**Fixed all 12 P0/P1/P2 findings from the Phase 10 Thermos review — classify-token reporting, unknown-engine graceful skip, emit-before-publish-failure, config/model-resolution dedup, adapter factory kwargs, duck-typing/envelope-unwrap/getattr cleanup, antigravity secret-alias declarative data, dead shim-adapter deletion, and a constrained review.py/flow.py internal split — with the full 819-test suite, ruff, actionlint, and zizmor all green via `scripts/ci-local.sh`.**

## Performance

- **Duration:** ~120 min
- **Completed:** 2026-07-01T15:09:21Z
- **Tasks:** 10 (9 code tasks + 1 verification gate)
- **Files modified:** 21 (3 new modules, 4 deleted shim files, 14 modified)

## Accomplishments

- All 12 in-scope Thermos findings (T-01 through T-12) fixed; T-13..T-18 (P3/info) left untouched as instructed.
- `emit_machine_output`'s compact tokens output now includes LLM-fallback classify cost (T-01); a bad `PREVUE_ENGINE` value degrades gracefully instead of crashing uncaught (T-03); machine output is always emitted even when check-publish fails (T-04).
- Consolidated: one canonical model-role resolver (`resolve_engine_models_from_config`) backing both dict- and typed-model entry points, plus a single `resolve_classify_model` ladder replacing two copy-pasted inline versions (T-08).
- `CliEngineAdapter` now constructor-only for `raw_args`/`pricing_override` — no more post-construction setter mutation with `isinstance` guards in `review.py` (T-07).
- `EngineAdapter.classify_with_tokens()` has a universal base-class default (T-09a); envelope-unwrap logic exists in exactly one place, `usage.unwrap_envelope_result` (T-09b); `output.py` reads `finding.severity` directly on a required typed field, no `getattr` fallback (T-12).
- `GEMINI_API_KEY` alias is declarative `CliEngineSpec` data; the two workflow files' antigravity install-skip comment blocks are deduped to one-liners that cross-reference each other (T-10).
- Deleted four dead backward-compat shim adapter files (`copilot_cli.py`, `claude_code_cli.py`, `cursor_cli.py`, `gemini_cli.py`); `review.py` no longer re-exports unused `output.py` names (T-11).
- `review.py` split into `review_config.py` (adapter factory kwargs + role-model resolution), `review_classify.py` (fallback-label merge bookkeeping + skill-refresh helpers), and `review_publish.py` (sticky/inline/check-run/emit publish sequence) — 1354 → 1208 lines, zero test-assertion changes (T-05, scope-constrained; see Deviations).
- `flow.py::review_with_retry` de-duplicated via `InvocationResult`/`_run_invocation`/`_merge_retry_tokens`, removing the duplicated invoke→capture→fence-extract sequence and the 3-4 near-duplicate token-meta call sites (T-06).
- Full CI-local gate passes: 819 tests green (90% coverage), `ruff check`/`ruff format --check` clean, `actionlint` clean, `zizmor` clean (T-10 gate task).

## Task Commits

1. **Task 1: T-01/T-03/T-04 review.py correctness bundle** - `feb7eef` (fix)
2. **Task 2: T-02 Claude secret rename migration callout** - `692b00c` (docs)
3. **Task 3: T-08 single model-resolution path** - `b5a1b6e` (refactor)
4. **Task 4: T-07 adapter factory replaces post-construction setters** - `f235d9e` (refactor)
5. **Task 5: T-09/T-12 duck-typing, envelope unwrap, getattr** - `dd4d907` (refactor)
6. **Task 6: T-10 antigravity secret alias as spec data + dedup** - `02373b9` (refactor)
7. **Task 7: T-11 delete shim adapters, drop review.py re-exports** - `4fed975` (refactor; docs/test-import completion folded into Task 8's commit — see Deviations)
8. **Task 8: T-05/finish-T-11 review.py monolith split** - `73f151e` (refactor)
9. **Task 9: T-06 extract flow.py retry/token-merge helpers** - `b1145ed` (refactor)
10. **Task 10: Full CI-local gate** - verification only, no commit (819 tests, ruff, actionlint, zizmor all green)

**Plan metadata:** (docs commit handled by orchestrator after this summary)

## Files Created/Modified

- `src/prevue/review_config.py` - `adapter_factory_kwargs()`/`resolve_role_models()` — review.py-local adapter/model wiring
- `src/prevue/review_classify.py` - `apply_fallback_labels()`, `refresh_matched()`, `skill_ratios()` — classify post-processing + skill-refresh helpers
- `src/prevue/review_publish.py` - `publish_review_result()` — sticky/inline/check-run/emit publish sequence
- `src/prevue/review.py` - classify-token merge, UnknownEngineError catch, emit-before-raise, adapter factory call, split delegation to the three new modules (1354 → 1208 lines)
- `src/prevue/cli.py` - unaffected by review.py changes; verified still correct via test_cli.py
- `src/prevue/config.py` - `_resolve_engine_models` delegates to `resolve_engine_models_from_config`; added `resolve_classify_model`
- `src/prevue/engines/registry.py` - `get_adapter`/`require_functional_adapter` accept `raw_args`/`pricing` factory kwargs
- `src/prevue/engines/cli_adapter.py` - constructor-only `raw_args`/`pricing_override`; `_build_env` loops `secret_env_aliases`; `_unwrap_classify_text` delegates to `usage.unwrap_envelope_result`
- `src/prevue/engines/base.py` - `EngineAdapter.classify_with_tokens()` default implementation
- `src/prevue/engines/flow.py` - `InvocationResult`, `_run_invocation`, `_merge_retry_tokens` extracted from `review_with_retry`; `_resolve_fence_source` delegates to `usage.unwrap_envelope_result`
- `src/prevue/engines/usage.py` - `unwrap_envelope_result()` shared envelope-unwrap helper
- `src/prevue/engines/spec.py` - `CliEngineSpec.secret_env_aliases` field; antigravity-cli sets `("GEMINI_API_KEY",)`
- `src/prevue/output.py` - `build_compact_output` reads `finding.severity` directly (no getattr)
- `src/prevue/classify/llm_fallback.py` - `_classify_batch` calls `classify_with_tokens` unconditionally
- `.github/workflows/prevue-review.yml` / `prevue-command-run.yml` - deduped antigravity install-skip comments
- `docs/consumer-setup.md` - "Breaking: Claude secret rename" migration section
- `docs/GETTING-STARTED.md` - cross-reference callout to the migration section
- `docs/ARCHITECTURE.md` / `docs/DEVELOPMENT.md` - module-tree updated to drop deleted shim files
- `tests/test_review_flow.py` - rewrote `test_engine_selection_via_prevue_engine`'s bad-engine assertion; two new regression tests (classify-tokens, emit-before-raise); `FindingsEngine` now inherits `EngineAdapter`
- `tests/test_config_precedence.py` - four new `resolve_classify_model` unit tests
- `tests/test_copilot_adapter.py` - migrated imports off the deleted `copilot_cli.py` shim; `CopilotCliAdapter()` → `get_adapter("copilot-cli")`
- `tests/test_cli.py` - `ClaudeAuthError` import moved to `prevue.engines.errors`
- **Deleted:** `src/prevue/engines/copilot_cli.py`, `claude_code_cli.py`, `cursor_cli.py`, `gemini_cli.py`

## Decisions Made

- **T-05 scope-constrained split (architectural discovery, documented here rather than a mid-execution checkpoint since it was resolvable without a design decision from the user):** The plan's literal design for `review_classify.py`/`review_publish.py` called for moving the entire classify→pack pipeline and the entire sticky/inline/check/emit tail into the new modules, with those modules calling `classify`, `llm_classify`, `upsert_sticky`, `conclude_review_check`, `post_inline_review`, etc. directly. Investigation showed `tests/test_review_flow.py` extensively uses `unittest.mock.patch("prevue.review.X", ...)` for ~21 distinct names (verified via grep across all four `--verify` test files). `unittest.mock.patch` replaces an attribute on the **module where the patched name is looked up at call time** — if a call site moves to a different module file, the original patch target becomes a dead reference and the code silently calls the *real* unpatched function instead. This would have broken dozens of tests while still reporting "passed" only if I'd also rewritten every affected assertion — directly violating the plan's explicit "every test... passes unmodified except one import-path update" requirement.
  Resolution: kept every physically-patched call site inside `review.py` (unchanged from before the split), and extracted only the code with zero patched-name calls into `review_config.py`/`review_classify.py` as pure functions. For the `review_publish.py` tail (which needs `upsert_sticky` via `_upsert_sticky_with_retry`, `post_inline_review`, `conclude_review_check`, `get_repo`, `emit_machine_output` — all patched), I applied a verified pattern (`import prevue.review as review; review.X(...)`, confirmed correct with a standalone circular-import scratch test) so the module-level lookup still resolves against `prevue.review`'s (patchable) namespace at call time, rather than binding a dead reference via a static `from prevue.review import X`.
  Net effect: `review.py` shrank 1354 → 1208 lines (not the plan's aspirational ~200, given the patch-target constraint), three new modules exist and are genuinely used, and all 819 tests pass with zero assertion changes (the plan's own fallback contingency — updating the single `_consumer_skills_root` test import — didn't even apply, since that helper stayed in `review.py` as an open-set/domain helper per the plan's own list).
- T-01/T-03/T-04: implemented exactly as specified in the plan, no deviations.
- T-02/T-07/T-08/T-09/T-10/T-11: implemented as specified.
- T-06 (flow.py): implemented as specified; `_token_meta`/`_retry_token_meta` kept unchanged (name/signature/behavior) since tests import them directly, confirmed via grep before starting.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `FindingsEngine` test double needed `EngineAdapter` base class**
- **Found during:** Task 5 (T-09a duck-typing removal)
- **Issue:** Removing `_classify_batch`'s `hasattr(adapter, "classify_with_tokens")` fallback meant a plain test double implementing only `classify()` (not inheriting `EngineAdapter`) would raise `AttributeError` when `classify_with_tokens` was called unconditionally — `test_run_review_fallback_fires_on_unmatched_paths` failed with an assertion mismatch (classify results came back empty instead of routed).
- **Fix:** Made `FindingsEngine` (the shared test double in `test_review_flow.py`) inherit from `EngineAdapter`, so its `classify()`-only subclasses (`SpyEngine`, `ClassifyEngine`) inherit the new base-class `classify_with_tokens()` default for free — exactly the fallback path the plan's Task 5 action anticipated ("if a test explicitly asserts the hasattr degrade path, update it to construct an adapter class that overrides classify only").
- **Files modified:** `tests/test_review_flow.py`
- **Verification:** Full suite green (819 tests) after the change.
- **Committed in:** `dd4d907` (Task 5 commit)

**2. [Rule 1 - Bug] Stale test assertion after T-04 fix in Task 1**
- **Found during:** Task 1 (T-04)
- **Issue:** No stale assertion existed prior to the fix; the new regression test needed to assert both the emit call AND the subsequent raise in the correct order.
- **Fix:** N/A — this was planned regression-test authoring, not a fix. No deviation; documented here only to clarify no surprises occurred.
- **Files modified:** none beyond the planned `tests/test_review_flow.py` additions.

**3. [Rule 2 - Missing Critical] `docs/ARCHITECTURE.md`/`docs/DEVELOPMENT.md` module-tree diagrams left stale after shim deletion**
- **Found during:** Task 7 (T-11 shim adapter deletion)
- **Issue:** Both docs listed `copilot_cli.py`/`claude_code_cli.py`/`cursor_cli.py`/`gemini_cli.py` as real module-tree entries; deleting the files without updating the docs would leave a documented file structure that doesn't exist on disk.
- **Fix:** Removed the four stale entries from `ARCHITECTURE.md`'s directory tree; replaced `DEVELOPMENT.md`'s stale per-engine-file list with the two files that actually exist (`spec.py`, `cli_adapter.py`).
- **Files modified:** `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`
- **Verification:** Content matches `src/prevue/engines/` directory listing post-deletion.
- **Committed in:** `73f151e` (folded into Task 8's commit after being caught unstaged from Task 7 — see note below)

**Process note (not a deviation, an execution-hygiene catch):** After committing Task 7, a routine `git status` check ahead of Task 8 revealed that four files legitimately edited during Task 7 (`docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`, `tests/test_cli.py`, `tests/test_copilot_adapter.py`) had never been staged — an earlier `git add -A -- <paths>` command partially failed on a nonexistent-path argument and the failure wasn't caught before committing. All four files' actual content was correct and already verified green in Task 7's own test run; they were folded into Task 8's commit with an honest combined commit message rather than force-amending the already-pushed-to-branch Task 7 commit. No functional impact — all commits before and after this correction pass the full test suite.

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug in a test double, 1 Rule 2 missing-critical doc update) + 1 architectural scope adjustment (T-05 split constrained by patch-target analysis, documented above as a decision) + 1 execution-hygiene catch (staging gap, corrected before it caused any commit to be broken).
**Impact on plan:** All auto-fixes were necessary for correctness (test double) or documentation accuracy (module tree). The T-05 scope adjustment was necessary to satisfy the plan's own "zero test-assertion changes" requirement — a literal reading of the plan's module-boundary suggestion would have violated that requirement. No scope creep beyond what each finding required.

## Issues Encountered

- **`unittest.mock.patch` + module-split risk (T-05):** see Decisions above — required careful verification (a standalone scratch-directory circular-import test) before committing to the lazy module-attribute-lookup pattern used in `review_publish.py`. This was the single highest-risk part of the task; verified correct before touching production code.
- **Pre-existing untracked review artifacts** (`10-THERMOS-REVIEW.md`, `10-THERMOS-SCOPE.patch`, `prevue-result.json`) were left untouched per the task constraints — confirmed not staged in any commit.
- **Pre-existing unstaged deletion** of `.planning/phases/10-boundary-contracts/10-THERMOS-FIXLIST.md` (present before this session started) was also left untouched and not staged in any of this task's commits.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 12 in-scope Thermos findings resolved; codebase is clean for the next phase (11: Skills as Pinned External Repo) to build on.
- `review.py`/`review_config.py`/`review_classify.py`/`review_publish.py` module boundaries are now established — future work extending the review pipeline should extend the appropriate module, being mindful of the patch-target constraint documented above if further extraction is attempted.
- T-13 through T-18 (P3/info findings) remain as explicit follow-up debt, not touched by this task, tracked in the original `10-THERMOS-REVIEW.md`.

---
*Phase: quick-260701-ju8*
*Completed: 2026-07-01*

## Self-Check: PASSED

- Created files verified on disk: `src/prevue/review_config.py`, `src/prevue/review_classify.py`, `src/prevue/review_publish.py`, this SUMMARY.md.
- Deleted files verified absent: `src/prevue/engines/copilot_cli.py`, `claude_code_cli.py`, `cursor_cli.py`, `gemini_cli.py`.
- All 9 task commit hashes verified present in `git log --oneline --all`: `feb7eef`, `692b00c`, `b5a1b6e`, `f235d9e`, `dd4d907`, `02373b9`, `4fed975`, `73f151e`, `b1145ed`.
- Full test suite (819 tests) + `ruff check` + `ruff format --check` + `actionlint` + `zizmor` all green via `scripts/ci-local.sh`.
