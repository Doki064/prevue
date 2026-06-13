---
phase: 06-reusable-workflow-hybrid-classification
verified: 2026-06-14T21:00:00Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Live sandbox consumer repo adoption (WKFL-01/02 success criterion #1)"
    expected: "Separate sandbox repo with minimal caller snippet from docs/consumer-setup.md pinned to a Prevue release tag receives sticky summary + prevue/review check on a normal PR; ambiguous-file PR shows cheap-model label or general-disclosure fallback; draft PR produces no run; bot/skip-review label PR posts neutral check + sticky skip reason without blocking required protection"
    why_human: "workflow_call E2E cannot be proven by unit tests or act; verified via live sandbox consumer UAT 2026-06-14"
    result: pass
---

# Phase 6: Reusable Workflow & Hybrid Classification Verification Report

**Phase Goal:** Any repo can adopt Prevue with a minimal caller snippet — the workflow self-checkouts, runs the full hybrid pipeline under minimal permissions, and respects consumer config and skip conditions

**Verified:** 2026-06-14T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Separate consumer repo adopts Prevue via `workflow_call` at pinned ref and gets a working review | ? HUMAN PENDING | `docs/consumer-setup.md` + `.github/workflows/prevue-review.yml` exist; static guards green; live sandbox Task 3 deferred per user — not a code gap |
| 2 | Reusable workflow self-checkouts Prevue at pinned non-main ref AND consumer at `pull_request.base.sha`, then runs single `uv run prevue review` | ✓ VERIFIED | `prevue-review.yml` L36-49 (dual checkout), L97-99 (single CLI); `test_reusable_workflow_yaml.py::test_two_checkouts` PASS |
| 3 | Run behavior configurable via workflow inputs and `.github/prevue.yml` from trusted base ref | ✓ VERIFIED | Inputs `engine`, `config-path`, `prevue-ref`; `PREVUE_CONFIG_PATH` set to `consumer/${{ inputs.config-path }}` (L103); `load_config()` single-read in `config.py`; `test_config.py` 7 tests PASS |
| 4 | Consumer typo in prevue.yml fails closed (`extra=forbid`) | ✓ VERIFIED | `SkipConfig`/`FallbackConfig` use `ConfigDict(extra="forbid")`; `test_config.py::test_extra_forbid_typo_fails` PASS |
| 5 | Clear-cut PRs spend zero classification tokens; ambiguous paths trigger cheap LLM fallback only for unmatched paths | ✓ VERIFIED | `classifier.py` surfaces `unmatched`; `review.py` L84-94 gates `llm_classify`; `test_llm_fallback.py` + `test_review_flow.py::test_run_review_fallback_skipped_when_all_matched` + `test_run_review_fallback_fires_on_unmatched_paths` PASS |
| 6 | Fallback failure degrades to `general` with disclosure — never red check | ✓ VERIFIED | `llm_fallback.py` L40-52 catch-all → `FALLBACK_DISCLOSURE`; `test_llm_fallback.py::test_degrade_to_general` PASS |
| 7 | Unknown cheap-model labels dropped against canonical set | ✓ VERIFIED | `_validate_labels` in `llm_fallback.py`; `test_engine_contract.py::test_classify_drops_unknown_labels` PASS |
| 8 | Thin `review.yml` dogfoods reusable workflow (no duplicated job body) | ✓ VERIFIED | `review.yml` L17-24 `uses: ./.github/workflows/prevue-review.yml`; `test_workflow_yaml.py::test_review_yml_uses_reusable_workflow` PASS |
| 9 | Workflow declares exactly `{contents:read, pull-requests:write, checks:write}`, named per-engine secrets `required:false`, no `secrets:inherit`, no `pull_request_target` | ✓ VERIFIED | `prevue-review.yml` L26-29, L18-24; `test_reusable_workflow_yaml.py` guards PASS; `docs/consumer-setup.md` permissions table |
| 10 | Draft PRs skipped at workflow `if:` guard (no runner spin) | ✓ VERIFIED | `prevue-review.yml` L33 `if: ${{ !github.event.pull_request.draft }}`; `test_reusable_workflow_yaml.py::test_draft_if_guard` PASS |
| 11 | Bot/label/title skips post NEUTRAL check + sticky reason before engine spend | ✓ VERIFIED | `skip.py` `should_skip()`; `review.py` L67-78 early-return; `conclude_skip_check(conclusion="neutral")`; `test_skip.py` 3 tests + `test_review_flow.py::test_run_review_bot_skip_neutral_no_engine` PASS |

**Score:** 10/11 truths verified (1 human-pending, 0 failed)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.github/workflows/prevue-review.yml` | Shippable `workflow_call` reusable workflow | ✓ VERIFIED | 104 lines; dual checkout, single CLI, draft guard |
| `.github/workflows/review.yml` | Thin dogfood caller | ✓ VERIFIED | 25 lines; `uses` local reusable workflow |
| `docs/consumer-setup.md` | Caller snippet + permissions + skip note | ✓ VERIFIED | Minimal snippet pinned `@v0.6.0`; permissions table |
| `src/prevue/config.py` | Single-read `load_config()` | ✓ VERIFIED | Rules/review/skip/fallback/engine unified; wired in `review.py` |
| `src/prevue/classify/llm_fallback.py` | Per-file LLM fallback | ✓ VERIFIED | `llm_classify()` with degrade-to-general |
| `src/prevue/skip.py` | Bot/label/title skip policy | ✓ VERIFIED | `should_skip()` returns reason or None |
| `src/prevue/engines/base.py` | `classify()` default-raising port | ✓ VERIFIED | L16-24 raises `NotImplementedError` |
| `src/prevue/engines/copilot_cli.py` | `classify()` subprocess impl | ✓ VERIFIED | L101-121 with `build_classify_prompt` |
| `src/prevue/engines/prompt.py` | Injection-safe classify prompt | ✓ VERIFIED | `build_classify_prompt()` with UNTRUSTED DATA fencing |
| `tests/test_reusable_workflow_yaml.py` | Static YAML guards | ✓ VERIFIED | 9 tests PASS |
| `tests/test_config.py` | Config loader contract | ✓ VERIFIED | 7 tests PASS |
| `tests/test_skip.py` | Skip policy contract | ✓ VERIFIED | 3 tests PASS |
| `tests/test_llm_fallback.py` | Fallback contract | ✓ VERIFIED | 3 tests PASS |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `review.yml` | `prevue-review.yml` | `uses: ./.github/workflows/prevue-review.yml` | ✓ WIRED | `test_workflow_yaml.py` asserts no `steps`/`runs-on` in caller job |
| `prevue-review.yml` | `src/prevue` | checkout `Doki064/prevue` → `.prevue` + `uv run prevue review` | ✓ WIRED | Pinned ref `v0.6.0` default; `persist-credentials: false` |
| `prevue-review.yml` | consumer config | `PREVUE_CONFIG_PATH` env | ✓ WIRED | Points to `consumer/.github/prevue.yml` on base ref |
| `review.py` | `load_config` | `consumer_path` from `PREVUE_CONFIG_PATH` | ✓ WIRED | L48-49; default `.github/prevue.yml` tested |
| `review.py` | `should_skip` | early-return before classify/engine | ✓ WIRED | L67-78; bot skip integration test PASS |
| `review.py` | `llm_classify` | fires when `result_cls.unmatched` non-empty | ✓ WIRED | L84-94; integration tests PASS |
| `llm_fallback.py` | `adapter.classify()` | selected engine instance | ✓ WIRED | L35-38; mock adapter tests PASS |
| `config.py` | `merge_rules`/`load_default_rules` | `_ruleset_from_raw` | ✓ WIRED | Consumer rules merged; `test_consumer_rules_applied` PASS |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `review.py` orchestration | `config` | `load_config(PREVUE_CONFIG_PATH)` reads consumer base-ref YAML | Yes — pydantic-validated sections | ✓ FLOWING |
| `review.py` skip path | `skip_reason` | `should_skip(pr, config.skip)` from PR metadata | Yes — bot/label/title from API | ✓ FLOWING |
| `review.py` classify path | `result_cls.unmatched` | `classify(reduced.files, ruleset.label_rules)` | Yes — per-file glob match scan | ✓ FLOWING |
| `llm_fallback.py` | `fallback_labels` | `adapter.classify(unmatched_paths, ...)` | Yes — subprocess JSON (mocked in tests) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Reusable workflow YAML guards | `uv run pytest tests/test_reusable_workflow_yaml.py -q` | 9 passed | ✓ PASS |
| Config + skip + fallback contracts | `uv run pytest tests/test_config.py tests/test_skip.py tests/test_llm_fallback.py -q` | 13 passed | ✓ PASS |
| Thin caller + dogfood wiring | `uv run pytest tests/test_workflow_yaml.py -q` | PASS (included in 40-test batch) | ✓ PASS |
| Skip before engine + fallback gating | `uv run pytest tests/test_review_flow.py::test_run_review_bot_skip_neutral_no_engine tests/test_review_flow.py::test_run_review_fallback_skipped_when_all_matched tests/test_review_flow.py::test_run_review_fallback_fires_on_unmatched_paths -q` | 3 passed | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — no phase-declared probes or `scripts/*/tests/probe-*.sh` for this phase.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| WKFL-01 | 06-02, 06-04 | Consumer calls reusable workflow with minimal snippet | ✓ SATISFIED (code) / ? HUMAN (live) | `prevue-review.yml` + `docs/consumer-setup.md`; live adoption pending |
| WKFL-02 | 06-02, 06-04 | Self-checkout + single CLI invocation | ✓ SATISFIED (code) / ? HUMAN (live) | Dual checkout + `uv run prevue review`; live E2E pending |
| WKFL-03 | 06-01, 06-03 | Config via inputs + prevue.yml from base ref | ✓ SATISFIED | `load_config()`, `PREVUE_CONFIG_PATH`, workflow inputs |
| WKFL-04 | 06-02 | Minimal scopes documented | ✓ SATISFIED | Permissions block + `docs/consumer-setup.md` table |
| CLSF-02 | 06-01, 06-03 | Hybrid LLM fallback for ambiguous diffs | ✓ SATISFIED | `llm_fallback.py` + engine `classify()` + review wiring |
| NOIS-01 | 06-02, 06-04 | Skip draft/bot/label/title by default | ✓ SATISFIED | Workflow draft `if:` + `skip.py` + neutral check path |

*Note:* `.planning/REQUIREMENTS.md` traceability table still marks NOIS-01 as Pending — implementation evidence contradicts that status; table lag only.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None | — | No TBD/FIXME/XXX/stub markers in phase-modified source files |

### Human Verification Required

### 1. Live Sandbox Consumer Repo Adoption (WKFL-01/02)

**Test:** Follow `06-04-PLAN.md` Task 3 steps: tag or `prevue-ref` override → add caller workflow in separate sandbox repo from `docs/consumer-setup.md` → open normal PR (sticky + check) → ambiguous-file PR (fallback label or general disclosure) → draft PR (no run) → bot or `skip-review` label PR (neutral check + sticky, non-blocking on required protection).

**Expected:** All six steps behave as documented; any A2/A4 degrade shows D-12 general-disclosure path (not crash/red); A3 neutral check neither blocks nor falsely passes.

**Why human:** `workflow_call` cannot be exercised by act or unit tests; requires real GitHub Actions in a second repository. Explicitly deferred per user request — not counted as automated gap.

### Gaps Summary

No automated gaps found. All code-level must-haves verified against the codebase (not SUMMARY claims). The sole remaining item is live sandbox consumer verification for WKFL-01/02 success criterion #1, routed to human verification per user instruction.

---

_Verified: 2026-06-14T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
