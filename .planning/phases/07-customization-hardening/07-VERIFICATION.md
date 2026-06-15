---
phase: 07-customization-hardening
verified: 2026-06-15T20:00:00Z
status: passed
score: 4/4
overrides_applied: 0
re_verification: false
---

# Phase 7: Customization & Hardening Verification Report

**Phase Goal:** Prevue behaves as a framework — consumers extend and override skills safely, prompt-injection defenses are verified, and every review proves the token-efficiency thesis with transparent budgets

**Verified:** 2026-06-15T20:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| 1 | Consumer repo adds custom skill bundle under `.github/prevue/skills/` and it is routed to; same-named consumer bundle overrides built-in | ✓ VERIFIED | `load_skills()` two-root merge in `src/prevue/skills/loader.py` (consumer overwrites builtin by `bundle/filename` key); `run_review()` resolves root via `PREVUE_CONSUMER_ROOT/.github/prevue/skills` and `select_skills()` on packed paths; workflow sets `PREVUE_CONSUMER_ROOT` in `.github/workflows/prevue-review.yml`; `tests/test_skills_merge.py` (6 tests) pass override/add-alongside/exclude/cap-skip |
| 2 | Untrusted PR text (titles, bodies, comments) never interpolated into engine prompts as instructions; prompt-injection red-team tested and documented as mitigated | ✓ VERIFIED | `DiffBundle` explicitly excludes title/body (`src/prevue/models.py:23`); prompts fence diff/paths in `UNTRUSTED DATA` + `INSTRUCTION_REASSERTION` tail (`src/prevue/engines/prompt.py`); `skip.py` reads `pr.title` for skip patterns only, never passed to engine; `tests/test_injection_adversarial.py` (3 tests) guard reassertion, classify fencing, gate independence; `SECURITY.md` + `docs/security.md` document four vectors |
| 3 | Summary comment reports tokens used and which skills loaded vs skipped on every review | ✓ VERIFIED | `run_review()` threads `token_meta` (review + classify, per-metric `~est`) and `skill_ratios` to `upsert_sticky()`; `render_body()` emits `Tokens:` line and `Skill coverage: N/M loaded — bundle ratios` plus named `Skills:` list (`src/prevue/github/comments.py:174-198`); packed-set coverage statement when files skipped (`:200-205`); `tests/test_comments.py` token/ratio/coverage tests pass |
| 4 | Oversized PRs reviewed within token budget using prioritized file packing, with explicit "N files not reviewed" disclosure | ✓ VERIFIED | `pack_files()` whole-file greedy pack with `make_file_weight()` risk ordering (`src/prevue/pack.py`); wired in `run_review()` with `max_input_tokens - output_reserve_tokens`; `conclude(partial=True)` → neutral (`src/prevue/gate.py:69-70`); sticky Coverage section + metadata count (`comments.py:200-222`); `tests/test_pack.py` (3 tests) + `test_run_review` budget integration (`not_reviewed_file_count == 1`) pass |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `src/prevue/skills/loader.py` | Two-root consumer/builtin merge, exclude, cap skip | ✓ VERIFIED | 145 lines; `consumer_skills_root`, `by_key.update(consumer_loaded)`, `return_skipped` |
| `src/prevue/pack.py` | Whole-file token packing | ✓ VERIFIED | `pack_files`, `make_file_weight` exported and used |
| `src/prevue/engines/tokens.py` | Token estimator | ✓ VERIFIED | `estimate_tokens` bytes/4 |
| `src/prevue/engines/prompt.py` | Injection fencing + reassertion | ✓ VERIFIED | `INSTRUCTION_REASSERTION` in both review and classify prompts |
| `src/prevue/engines/flow.py` | Token meta on all result paths | ✓ VERIFIED | `_token_meta()` in success, degrade, retry paths |
| `src/prevue/review.py` | Pack + skills + transparency wiring | ✓ VERIFIED | Full pipeline: pack → classify → load_skills → engine → sticky with meta |
| `src/prevue/github/comments.py` | Token/skills/coverage sticky sections | ✓ VERIFIED | `render_body` accepts and renders all transparency kwargs |
| `src/prevue/gate.py` | Partial → neutral | ✓ VERIFIED | `conclude(..., partial=True)` returns `"neutral"` |
| `tests/test_injection_adversarial.py` | CI regression guard | ✓ VERIFIED | 3 tests collected, pass in suite |
| `tests/test_skills_merge.py` | Consumer merge tests | ✓ VERIFIED | 6 tests, fixtures on disk |
| `tests/test_pack.py` | Packing tests | ✓ VERIFIED | 3 tests |
| `tests/test_tokens.py` | Estimator test | ✓ VERIFIED | 1 test |
| `SECURITY.md` | Trust boundary + mitigations | ✓ VERIFIED | Four vectors table, SKIL-04, no title/body to engines |
| `docs/examples/prevue.yml` | Starter config (07-07) | ✓ VERIFIED | Full commented starter with skills/review/classification sections |
| `docs/consumer-setup.md` | Links starter + configuration | ✓ VERIFIED | Links `./examples/prevue.yml` and `./configuration.md` |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `review.py` | `pack.py` | `pack_files(reduced.files, weight=..., budget_tokens=pack_budget)` | ✓ WIRED | Lines 131-136 |
| `review.py` | `skills/loader.py` | `load_skills(consumer_skills_root=_consumer_skills_root(), ...)` | ✓ WIRED | Lines 200-207 |
| `review.py` | `github/comments.py` | `upsert_sticky(..., token_meta=..., skill_ratios=..., skipped_paths=...)` | ✓ WIRED | Lines 256-282 |
| `engines/flow.py` | `engines/tokens.py` | `estimate_tokens(prompt) + estimate_tokens(stdout)` | ✓ WIRED | `_token_meta()` |
| `engines/prompt.py` | `INSTRUCTION_REASSERTION` | Appended after final `~~~` in both builders | ✓ WIRED | Lines 89, 162 |
| `review.py` | `result.engine_meta['engine']` | `engine.name` after review | ✓ WIRED | Line 217; sticky reads via `engine_meta.get('engine')` |
| `docs/consumer-setup.md` | `docs/examples/prevue.yml` | Markdown link | ✓ WIRED | Line 55 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `render_body()` token line | `token_meta.review`, `token_meta.classify` | `flow._token_meta()` + `estimate_classify_tokens()` in `run_review()` | Yes — computed from prompt/stdout bytes, not hardcoded | ✓ FLOWING |
| `render_body()` skill ratios | `skill_ratios` dict | `_skill_ratios(skills, matched)` from loaded skill lists | Yes — derived from actual bundle counts | ✓ FLOWING |
| `render_body()` skipped files | `skipped_paths` | `[f.path for f in skipped_files]` from `pack_files()` | Yes — real packed/skipped split | ✓ FLOWING |
| `render_body()` loaded skills | `loaded_skills` | Matched skills with `source` tag from loader | Yes — includes consumer/builtin distinction | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full test suite | `uv run python -m pytest -q --tb=short` | 351 passed in 0.89s | ✓ PASS |
| Injection adversarial suite | `pytest --collect-only tests/test_injection_adversarial.py` | 3 tests collected | ✓ PASS |
| Consumer skill merge | `pytest --collect-only tests/test_skills_merge.py` | 6 tests collected | ✓ PASS |
| Token packing | `pytest --collect-only tests/test_pack.py` | 3 tests collected | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — no phase-declared probes or conventional `scripts/*/tests/probe-*.sh` for this phase.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| SKIL-03 | 07-04 | Consumer custom skills + override via `.github/prevue/skills/` | ✓ SATISFIED | `loader.py` merge; workflow `PREVUE_CONSUMER_ROOT`; merge tests |
| SECR-02 | 07-05 | Untrusted PR text not in prompts; injection tested & documented | ✓ SATISFIED | `DiffBundle` exclusion; adversarial tests; `SECURITY.md` |
| OUTP-04 | 07-03 | Summary token/cost transparency + skills loaded vs skipped | ✓ SATISFIED | `render_body` token + skill coverage lines; review wiring |
| DIFF-03 | 07-02 | Token budget packing + "N files not reviewed" disclosure | ✓ SATISFIED | `pack.py` + sticky Coverage section + partial neutral gate |

No orphaned requirements — all four Phase 7 requirement IDs appear in ROADMAP and are implemented.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | None in phase-modified `src/prevue/` files | — | — |

Scanned phase-modified files from `07-REVIEW.md` list: no `TBD`/`FIXME`/`XXX`/`TODO`/`PLACEHOLDER` debt markers in production code. No disabled/skipped/xfail tests in `tests/`.

**Note (info, not gap):** Malformed consumer skills raise `ValidationError` from `load_skills()`; `cli.py` catches generic exceptions and exits 1 (workflow fail-closed) but does not publish a Prevue red *check run* before the exception. Skill content never reaches the engine. Documented in `SECURITY.md`; loader-level fail-closed verified by `test_malformed_consumer_fails`.

### Human Verification Required

None pending. D-08 engine tool posture (vector 4) is code-audited (adapters invoke CLIs without `--allow-tool` flags: `copilot -s --no-ask-user`, `claude --bare -p`, `cursor-agent -p -f`) and was human-verified in `07-UAT.md` Test 7 (pass). `SECURITY.md` recommends live re-verify before production — informational, not blocking v1.0 milestone closure.

### Gap-Closure Plans (07-06, 07-07)

| Truth | Status | Evidence |
| ----- | ------ | -------- |
| Sticky Engine line reflects actual adapter (not hardcoded copilot-cli) | ✓ VERIFIED | `review.py:217` sets `engine_meta['engine']`; `test_render_body_engine_from_meta` asserts `Engine: cursor-cli` |
| Consumer skills tagged `(bundle, consumer)` in sticky | ✓ VERIFIED | `review.py:260-264`; `test_render_body_skill_consumer_source` |
| Copy-paste starter `docs/examples/prevue.yml` + consumer-setup links | ✓ VERIFIED | File exists; `consumer-setup.md:55,87` link starter and configuration |

### Gaps Summary

No gaps found. All four ROADMAP success criteria are implemented, wired through `run_review()` → sticky comment, regression-tested (351 tests green), and documented. Phase 7 goal achieved.

---

_Verified: 2026-06-15T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
