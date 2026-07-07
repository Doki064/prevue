---
phase: 10-boundary-contracts
verified: 2026-07-06T08:00:00Z
status: human_needed
score: 24/25 truths verified (code-level); 1 (live real-token capture) unconfirmed pending a live CI run
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 21/21
  gaps_closed:
    - "10-UAT.md gap 1 THIRD RECURRENCE (Copilot CLI real-token OTEL capture silently no-op'd because cli_adapter.py's review() pre-created the per-call otel_path as an empty directory via tempfile.mkdtemp — the real, CI-pinned Copilot CLI 1.0.67 file exporter only writes its span file when the exact configured path does not already exist as anything): fixed in plan 10-11 by replacing tempfile.mkdtemp(dir=base_otel_dir) with os.path.join(base_otel_dir, f'{uuid.uuid4().hex}.jsonl') — a non-filesystem-touching, still-unique-per-call path construction. Verified present in src/prevue/engines/cli_adapter.py:236-247 (import uuid at line 12; os.makedirs(base_otel_dir, exist_ok=True) precedes it, only the base dir is created, not the leaf path)."
    - "Regression test added/updated: tests/test_copilot_adapter.py::TestOtelPerCallIsolation::test_two_calls_get_distinct_otel_paths now asserts `not os.path.exists(p)` and `p.endswith('.jsonl')` for both per-call paths — fails immediately if a future change reintroduces pre-creating the OTEL leaf path on disk. test_makedirs_oserror_degrades_to_job_wide_dir_instead_of_crashing correctly re-targets the OSError-degrade test at os.makedirs (the only remaining filesystem call in the new construction) since tempfile.mkdtemp is no longer called by production code."
    - "Full test suite verified green independently in this session: `uv run pytest tests/test_copilot_adapter.py -x -q` = 41 passed; `uv run pytest -x -q` (whole workspace, run once) = 835 passed, zero regressions."
    - "Debug log (.planning/debug/copilot-otel-real-capture-recurrence.md) and 10-UAT.md gap 1 both updated with a 'Fix Applied'/`fix_update_2026-07-06_FOURTH_ROUND` entry — both explicitly and correctly withhold 'resolved'/passing status, stating live re-verification against a real GitHub Actions run with a real COPILOT_GITHUB_TOKEN is still required. This is the correct call: three prior code-level-verified fixes for this exact gap (10-09 parser rewrite, an intermediate CR-01/CR-02 fix round, and 10-10 argv/-p delivery mode) all passed code review and unit tests but failed live re-verification. This verification session found no evidence of a fourth live run since 10-11 landed (no PR-run transcript, no updated UAT test-1 status, no file newer than the 10-11 commits documenting a live pass) — so the gap is correctly still open pending human/live confirmation, not silently closed by code inspection."
  gaps_remaining:
    - "PERF-03 live confirmation: sticky comment showing real (non-~est) Copilot token counts end-to-end in a live GitHub Actions run has not yet been demonstrated for this specific fix (10-11). This is the fourth code-level fix attempt for the same underlying truth; the project's own established discipline for this recurring item requires live evidence before closing it — this verification session honors that discipline and does not mark it passed from code/tests alone."
  regressions: []
  new_findings:
    - "10-REVIEW.md (re-review after 10-11, 2026-07-06T07:00:00Z) surfaced a new WR-01: because a single review() call's first and retry invocations share the exact same otel_path, and the real Copilot exporter only writes when the exact path does not already exist, a retried Copilot call's own OTEL span is silently never written (the first invocation's write already occupies the path). This degrades safely via the existing _otel_capture_grew / _partial_estimate_retry_tokens fallback (no crash, no corrupted totals) but silently under-counts real usage/cost for retried otel-jsonl reviews specifically, and is untested. Not a regression introduced by 10-11 (the pre-fix code had the same one-path-per-call design, just under a different failure mode where neither invocation ever got real capture) — but it is a newly-exposed, real accuracy gap now that the path IS usable. Tracked as a warning, not a blocker: the core UAT gap 1 truth concerns single-call capture, and does not regress."
---

# Phase 10: Boundary Contracts Verification Report

**Phase Goal:** Stabilize the highest-churn-cost boundaries — config resolution, the engine-adapter contract, and machine-readable output — before more adapters and config knobs accrue and make every change N× more expensive to retrofit.
**Verified:** 2026-07-06T08:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap-closure plan 10-11 (commits `9c62bba` fix, `7d3420d` docs, `3a7450e` summary), the FOURTH round of fixing 10-UAT.md gap 1 (Copilot CLI real-token OTEL capture), followed by a code-review re-pass (`10-REVIEW.md`) and a full external Thermos review (`10-THERMOS-REVIEW.md`) of the entire phase-10 branch.

## Goal Achievement

### Observable Truths

Truths 1–18 are unchanged since the prior verification round (2026-07-05) and were regression-checked directly against the current codebase in this session (spec.py, cli_adapter.py structure outside the touched otel_path lines, config.py, pricing/__init__.py, errors.py, llm_fallback.py, output.py, review.py call sites, workflow YAML). No drift found. Truths 19–21 (the 10-10 argv/-p delivery fix) also remain intact and are re-confirmed below, alongside the new 10-11-specific truths (22-24) and the one still-open truth (25).

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | One concrete CliEngineAdapter implements review/classify/classify_skills once for all CLI engines | VERIFIED (regression check) | `src/prevue/engines/cli_adapter.py` structure unchanged outside `review()`'s otel_path lines |
| 2 | Registry auto-populates by iterating CLI_ENGINE_SPECS | VERIFIED (regression check) | `registry.py` / `spec.py:CLI_ENGINE_SPECS` unchanged |
| 3 | Adding a CLI engine is one CliEngineSpec data entry | VERIFIED (regression check) | `spec.py` `CLI_ENGINE_SPECS` tuple unchanged, 4 entries |
| 4 | Config resolution order is declared, documented, and tested | VERIFIED (regression check) | `config.py:43` `CONFIG_PRECEDENCE = "workflow input > .github/prevue.yml > built-in defaults"`; `tests/test_config_precedence.py` green |
| 5 | engine.raw_args is a list[str]; shell string rejected | VERIFIED (regression check) | `_validate_raw_args` unchanged; `tests/test_raw_args.py` green |
| 6 | Per-role models resolve: models.<role> else engine.model else engine default | VERIFIED (regression check) | `config.py:95,301` unchanged; model_roles tests green |
| 7 | compute_cost applies cache-aware formula; vendored pricing snapshot | VERIFIED (regression check) | `pricing/__init__.py` WR-01 null-override fallback intact; `tests/test_pricing.py` green |
| 8 | run_review emits compact machine-readable output to $GITHUB_OUTPUT | VERIFIED (regression check) | `output.py:23,72` `build_compact_output`/`emit_machine_output` unchanged; see Warnings re: cost/token completeness below |
| 9 | cursor-cli invokes cursor-agent with --output-format json; envelope unwrapped via result field | VERIFIED (regression check) | `spec.py` cursor-cli block unchanged |
| 10 | cursor-cli's estimated=True is backed by verified envelope-schema fact | VERIFIED (regression check) | unchanged |
| 11 | antigravity-cli is functional=False; require_functional_adapter fails closed | VERIFIED (regression check) | unchanged |
| 12 | get_adapter('antigravity-cli') still resolves despite functional=False | VERIFIED (regression check) | unchanged, test green |
| 13 | require_functional_adapter used at engine-selection call site | VERIFIED (regression check) | `review.py` call site unchanged |
| 14 | Consumer-facing docs no longer claim antigravity-cli is selectable | VERIFIED (regression check) | `docs/configuration.md` unchanged |
| 15 | usage.py::_parse_copilot_otel correctly parses the real Copilot CLI flat-span JSONL schema | VERIFIED (regression check) | Parser itself untouched by 10-11 (plan explicitly did not modify it — its existing `path.is_dir()`/`else: [path]` branch already handles a file-shaped `otel_path`); `tests/test_usage_capture.py` green |
| 16 | Consumers can override the review model via workflow input/env, taking precedence over `.github/prevue.yml` | VERIFIED (regression check) | `.github/workflows/prevue-review.yml` `PREVUE_MODEL` wiring intact |
| 17 | Downstream jobs can chain automation on prevue's job outputs via `needs.<job>.outputs.*` | VERIFIED (regression check) | top-level `on.workflow_call.outputs:` block intact |
| 18 | CR-01 (sanitize_stderr redact-before-truncate) and its regression tests remain intact | VERIFIED (regression check) | `errors.py:14-25` unchanged |
| 19 | copilot-cli's real invocation shape reaches Copilot CLI 1.0.67's OTEL-emitting `-p` code path for prompts under the 64 KiB ceiling | VERIFIED (regression check) | `spec.py` `prompt_delivery="stdin-or-argv"`, `argv_prompt_max_bytes=65_536` unchanged; independently live-confirmed reachable per 10-UAT.md `fix_update_2026-07-06_THIRD_RECURRENCE` (PR #15: `-p` path IS reached live) |
| 20 | Large-diff PRs never regress to the 01-07 ARG_MAX crash | VERIFIED (regression check) | `cli_adapter.py` oversized-prompt stdin fallback unchanged; test green |
| 21 | raw_args still land LAST in argv on both delivery branches | VERIFIED (regression check) | unchanged |
| 22 | **(NEW, 10-11) `review()` no longer pre-creates the per-call OTEL path as a directory before invoking Copilot** — path is constructed via `os.path.join`+`uuid4().hex` and left non-existent so Copilot's file exporter can create it as a regular file | VERIFIED | `cli_adapter.py:236-247`: `os.makedirs(base_otel_dir, exist_ok=True)` then `otel_path = os.path.join(base_otel_dir, f"{uuid.uuid4().hex}.jsonl")` — no `tempfile.mkdtemp` call remains anywhere in the file (`grep -c tempfile.mkdtemp` = 0); `import uuid` present at line 12 |
| 23 | **(NEW, 10-11)** Per-call OTEL path uniqueness (WR-01's original goal) preserved | VERIFIED | `tests/test_copilot_adapter.py::test_two_calls_get_distinct_otel_paths`: two sequential `review()` calls produce two distinct paths, both under `base_otel_dir`, both ending `.jsonl`, both asserted `not os.path.exists(p)` — test passes |
| 24 | **(NEW, 10-11)** A regression test fails if the OTEL path is ever pre-created on disk again | VERIFIED | Same test above asserts `assert not _os.path.exists(p)` per path — this is a real, executable regression guard, not a doc claim; ran it: passes against current code, would fail against a `tempfile.mkdtemp`-style reintroduction |
| 25 | **(GAP, still open) Live end-to-end confirmation:** real Copilot CLI, real CI, real token, real PR shows real (non-`~est`) token counts in the sticky comment, using the 10-11-fixed code | FAILED / UNCONFIRMED | No evidence found of a live run since the 10-11 commits (`9c62bba`, `7d3420d`, `3a7450e`) landed. 10-UAT.md gap 1's `status:` field is still `failed` (correctly, per the plan's own success criteria); no live-test transcript exists adjacent to `fix_update_2026-07-06_FOURTH_ROUND`. This is the fourth code-level-verified-but-live-unconfirmed round for this exact truth — routed to Human Verification below, not marked passed |

**Score:** 24/25 truths verified at the code level; 1 (truth 25, the live-capture confirmation) is the one item this verification correctly does NOT pass on code inspection alone, per the explicit gap-closure discipline recorded in this phase's own plan/UAT/debug-log wording.

### Deferred Items

None — no gaps identified in this round match a later phase's stated scope. The Thermos-review-identified accounting-completeness warnings (classify/skill-select cost/token omission — WR-T01/T02/T03) and structural-debt warnings (`review.py`/`flow.py` size — WR-T07/T08) are explicitly tracked by Thermos as "before phase 11" follow-ups, not phase-10 blockers, and are reported as Warnings below rather than deferred gaps (they were known and open at the prior verification pass too — not newly discovered scope creep).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/prevue/engines/cli_adapter.py` | `otel_path` built via `os.path.join(base_otel_dir, f"{uuid.uuid4().hex}.jsonl")`, not `tempfile.mkdtemp` | VERIFIED | Lines 236-247; `import uuid` line 12; `grep -n "tempfile.mkdtemp"` returns 0 matches in the file |
| `tests/test_copilot_adapter.py` | `TestOtelPerCallIsolation` asserts path never pre-created; OSError test patches `os.makedirs` | VERIFIED | `test_two_calls_get_distinct_otel_paths` (renamed), `test_makedirs_oserror_degrades_to_job_wide_dir_instead_of_crashing` (renamed) both present and passing; 41/41 tests in file pass |
| `.planning/debug/copilot-otel-real-capture-recurrence.md` | "Fix Applied" section recording the diff shape, correctly withholding resolution | VERIFIED | Appended section present, matches plan/summary claims verbatim |
| `.planning/phases/10-boundary-contracts/10-UAT.md` | Gap 1 `fix_update_2026-07-06_FOURTH_ROUND` field appended; `status: failed` preserved | VERIFIED | Present at lines 278-291; `status: failed` at line 195 unchanged |
| All 10-10 and earlier artifacts (spec.py, config.py, pricing, errors.py, output.py, workflow YAML) | Unchanged/intact | VERIFIED (regression) | No drift detected |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli_adapter.py`'s new `otel_path` construction | `usage.py::_parse_copilot_otel` | `COPILOT_OTEL_FILE_EXPORTER_PATH` env var, consumed via existing `path.is_dir()`/`else: [path]` branch | WIRED | Parser unmodified; plan explicitly and correctly relied on the existing file-path branch already covering this shape — confirmed by reading `usage.py`, no `is_dir()` special-casing needed for a file leaf |
| `cli_adapter.py`'s `-p` argv branch (10-10) | Copilot CLI 1.0.67's OTEL file exporter (external) | `copilot -s --no-ask-user -p "<prompt>"` invocation shape | WIRED locally / live-confirmed for the invocation shape (PR #15) but NOT yet live-confirmed for the 10-11-fixed path construction specifically | The 10-11 fix has not itself been exercised against the real binary in CI since landing — only local `os.makedirs`/path-construction unit assertions and the debug session's manual local reproduction of the underlying bug support it |
| `.github/workflows/prevue-review.yml` (`COPILOT_OTEL_FILE_EXPORTER_PATH`) | `usage.py::_parse_copilot_otel` | env-read → capture_usage dispatch | WIRED (regression check) | Unchanged |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `cli_adapter.py`'s `otel_path` construction | `otel_path` (str \| None) | `os.path.join(base_otel_dir, f"{uuid.uuid4().hex}.jsonl")`, computed after `os.makedirs(base_otel_dir, exist_ok=True)` | Yes — path is a real, unique, non-pre-existing string handed to the subprocess env; verified via unit test that it is never pre-created and always ends `.jsonl` | FLOWING (locally) |
| `usage.py::_parse_copilot_otel` reading that path in production | Token totals | Real flat-span JSONL Copilot's exporter is now expected to create at that exact path | UNCONFIRMED — no live-CI evidence collected post-10-11 that the real binary actually writes to this exact new construction end-to-end (the debug session's reproduction used its own manually-constructed leaf-path value, not a re-run of this exact production code path against the real CLI since the fix landed) | UNCONFIRMED LIVE (see Human Verification) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `otel_path` is never pre-created on disk (regression guard) | `uv run pytest tests/test_copilot_adapter.py::TestOtelPerCallIsolation -q` | 3 passed | PASS |
| Full workspace suite has zero regressions from the 10-11 diff | `uv run pytest -x -q` (run once, whole suite) | 835 passed | PASS |
| No `tempfile.mkdtemp` remains in `cli_adapter.py` | `grep -c "tempfile.mkdtemp" src/prevue/engines/cli_adapter.py` | 0 | PASS |
| `uuid` import and usage present | `grep -n "^import uuid\|uuid.uuid4" src/prevue/engines/cli_adapter.py` | 2 matches (import line 12, usage line 242) | PASS |
| Live real-token capture end-to-end (real Copilot CLI + real CI + real PR) | N/A — requires a live GitHub Actions run with a real `COPILOT_GITHUB_TOKEN`; cannot be run from this verification session | Not run | SKIP → routed to Human Verification |

### Probe Execution

No dedicated `scripts/*/tests/probe-*.sh` files exist in this repository (Python/pytest project, not the shell-probe convention this step targets). Skipped — no runnable probes declared in any 10-* PLAN/SUMMARY.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| ENGN-10 | 10-01..10-02 | Consolidate CLI engine adapters into one generic adapter + spec registry | SATISFIED | `spec.py:CLI_ENGINE_SPECS`, `cli_adapter.py:CliEngineAdapter` — single class for all 4 engines; unchanged this round |
| WKFL-05 | 10-03..10-04 | Declared, documented, tested config precedence | SATISFIED | `config.py:43` `CONFIG_PRECEDENCE` constant; `tests/test_config_precedence.py` green |
| PERF-03 | 10-05..10-09, 10-10, 10-11 (this plan) | Actual token accounting replacing bytes/4 estimate, engine-reported usage | **PARTIALLY SATISFIED — code-complete, live-unconfirmed** | Parser, env wiring, CLI version pin, invocation-shape (`-p`), and now the OTEL-path-construction fix are all present and unit/integration-tested; REQUIREMENTS.md marks PERF-03 `[x]` complete, but 10-UAT.md gap 1 (the live behavioral truth this requirement exists to deliver) explicitly and currently reads `status: failed` — a real discrepancy between the requirements checklist and the live-verified state of the system. This report does NOT independently flip PERF-03 to fully resolved; see Human Verification |
| ENGN-08 | 10-03 | Adapter raw-args passthrough, list[str] only | SATISFIED | `_validate_raw_args`, tests green; `raw_args` ordering re-confirmed on both 10-10 delivery branches |
| ENGN-09 | 10-06 | Per-role model tiering | SATISFIED | `config.py:95,301` resolution order; tests green |
| OUTP-05 | 10-07..10-08 | Structured machine-readable review output | SATISFIED (core contract) — with tracked incompleteness | `output.py:build_compact_output`/`emit_machine_output` wired to `$GITHUB_OUTPUT` and `workflow_call.outputs`; however Thermos review (WR-T01/T02/T03) found classify/skill-select token/cost spend is not folded into the reported `tokens`/`cost_usd` output fields — an accuracy-completeness gap in an already-shipped feature, not a missing artifact. Tracked as a Warning, not a blocker (pre-existing, not new, has a documented follow-up path) |

No orphaned requirements found — all 6 IDs mapped to this phase in REQUIREMENTS.md appear in at least one 10-* PLAN's `requirements` field (cross-checked: ENGN-10 in 10-01/10-02, WKFL-05 in 10-03/10-04, PERF-03 in 10-05 through 10-11, ENGN-08 in 10-03, ENGN-09 in 10-06, OUTP-05 in 10-07/10-08).

### Anti-Patterns Found

No new debt markers (`TBD`/`FIXME`/`XXX`) introduced by the 10-11 diff. `grep -n "TBD\|FIXME\|XXX" src/prevue/engines/cli_adapter.py tests/test_copilot_adapter.py` returns no matches. No placeholder/stub patterns in the touched lines — the change is a genuine one-line production fix plus corresponding test updates, exactly as scoped.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| n/a | — | — | — | No anti-patterns found in the 10-11 diff itself |

Carried-forward warnings from the independent Thermos external review (`10-THERMOS-REVIEW.md`, 0 critical / 10 warning / 3 info) and the post-10-11 code review (`10-REVIEW.md`, 0 critical / 1 warning / 1 info) are summarized below for completeness — none are new blockers, all are pre-existing or explicitly tracked as non-blocking follow-ups:

- **WR-T01/T02/T03** (Thermos): classify/skill-select Copilot spend and skill-select tokens are omitted from reported `cost_usd`/`tokens` in the sticky comment and `$GITHUB_OUTPUT`. Pre-existing, documented, tracked for phase 11.
- **WR-T05** (Thermos): `docs/DEVELOPMENT.md`/`docs/TESTING.md` still describe deleted per-engine adapter classes (import errors for contributors following docs). Non-blocking doc debt.
- **WR-T07/T08** (Thermos): `review.py` (~1,208 lines) and `flow.py` (634 lines, +471 from base) remain god-modules; explicitly flagged as phase-11 risk (consolidate-model wiring landing in the same function), not a phase-10 blocker.
- **New WR-01** (10-REVIEW re-review, post-10-11): a single `review()` call's first and retry invocations share one `otel_path`; because the real exporter only writes when the exact path doesn't already exist, a retry's own OTEL span is silently never captured (falls back safely to partial-estimate blending, no crash/corruption). This is a newly-*exposed* accuracy gap (the fix makes the path usable, which is when this asymmetry becomes observable) rather than a regression from 10-11's stated goal. Not required by this plan's must-haves; tracked as a follow-up.

### Human Verification Required

### 1. Live GitHub Actions confirmation of real (non-`~est`) Copilot token capture, post-10-11 fix

**Test:** Trigger a real Copilot-CLI-engine review run in GitHub Actions CI, using a real `COPILOT_GITHUB_TOKEN` secret, on a PR whose assembled review prompt is comfortably under the 64 KiB `argv_prompt_max_bytes` ceiling (so the `-p`/argv delivery branch is unambiguously exercised) and with `review.max_review_calls == 1` (a single invocation, avoiding the newly-surfaced retry-path OTEL-reuse gap noted above, which is a separate known issue).

**Expected:** The sticky PR comment's Tokens line shows real, non-`~est`-labeled token counts (`engine_meta["tokens"]["estimated"] is False`), demonstrating the full chain — workflow env → real Copilot CLI subprocess invoked with `-p` → OTEL file write to the new `os.path.join`/`uuid4()`-constructed path → `_parse_copilot_otel` read — works end-to-end in production with the 10-11 fix specifically in place.

**Why human:** This is the fourth code-level fix for this exact recurring gap (10-UAT.md gap 1). The first three (10-09 parser rewrite, an intermediate CR-01/CR-02 fix round, and 10-10's argv/-p delivery mode) each passed unit tests, code review, and static/local reproduction, and each was subsequently found broken in production during a real live run — for three *different* root causes each time. Given that history, this verification session deliberately does not certify the live-behavior truth from code inspection or unit tests alone, per the project's own established discipline for this specific item (recorded consistently across 10-UAT.md, the debug log, and this plan's own success criteria, which withhold `resolved` status pending exactly this check). No evidence of a post-10-11 live run was found in this session (no new UAT test-1 status change, no live-run transcript, no file timestamped after the 10-11 commits documenting a pass).

**Also worth confirming while doing the above:** whether `review.max_review_calls > 1` retry scenarios need a follow-up fix for the newly-surfaced same-`otel_path`-reuse gap (10-REVIEW.md's new WR-01) — out of scope for closing gap 1 itself (which concerns single-call capture), but worth a conscious decision on whether it needs its own gap-closure round before phase 11.

### Gaps Summary

Phase 10's structural work (engine-adapter consolidation, config precedence, per-role models, raw-args passthrough, machine-readable output contract, cursor-cli/antigravity-cli handling) is solid and unchanged/regression-clean across 4 verification passes plus one external (Thermos) review. Plan 10-11's fix for the THIRD recurrence of the Copilot OTEL real-token-capture bug is itself correctly implemented, code-reviewed, and unit-tested: `otel_path` is now built as a non-pre-existing, uniquely-named file path instead of a pre-created empty directory, matching the exact root cause the debug session identified via direct reproduction against the real, CI-pinned Copilot CLI 1.0.67 binary.

However — and this is the one thing this verification will not paper over — the underlying behavioral truth this whole four-round effort exists to deliver (real, non-estimated token/cost reporting for copilot-cli in production CI) has not been reconfirmed against a real live GitHub Actions run since this specific fix landed. Given that the exact same "code-level pass, live fail" pattern has occurred three times before for this exact gap, for three different underlying causes each time, this report intentionally routes that single item to human/live verification rather than marking it passed. Everything else in the phase remains fully verified and stable.

---

_Verified: 2026-07-06T08:00:00Z_
_Verifier: Claude (gsd-verifier)_
</content>
