---
phase: 10-boundary-contracts
generated: 2026-06-30
branch: gsd/phase-10-boundary-contracts
pr: https://github.com/Doki064/prevue/pull/31
audience: Sonnet 4.6 (fix pass)
reviews: thermo-nuclear-review + thermo-nuclear-code-quality-review
scope: origin/main...HEAD excluding .planning/** and model_prices.json
---

# Phase 10 Thermos Fix List

Unified findings from parallel thermo branch-audit + code-quality passes. **Findings first, deduplicated.** Overlapping items weighted higher.

**Already fixed locally (uncommitted)** — CR-01 doc drift partial pass:
- `SECURITY.md` D-08 invocation strings (Claude/Cursor/Antigravity)
- `docs/configuration.md` — `claude-code-oauth-token` / `CLAUDE_CODE_OAUTH_TOKEN`
- `docs/consumer-setup.md`, `README.md` — same secret rename
- `.github/workflows/prevue-command-run.yml` — `CLAUDE_CODE_OAUTH_TOKEN` from `secrets.CLAUDE_CODE_OAUTH_TOKEN`

---

## Verdict

| Reviewer | Verdict |
|----------|---------|
| Branch audit | **3 merge blockers** (OTEL path, model precedence, doc sweep) |
| Code quality | **Do not approve** — `review.py` god-file growth, config round-trip, conflated spec axes |

Behavior mostly works (795 tests green). Fix blockers + structural debt before merge or schedule follow-up phase.

---

## P0 — Merge blockers (bugs / breakage)

### T-01 · Copilot OTEL capture broken in CI
**Sources:** branch audit #1  
**Severity:** High

| Location | Issue |
|----------|-------|
| `.github/workflows/prevue-review.yml:154` | `COPILOT_OTEL_FILE_EXPORTER_PATH` set to directory (`runner.temp/copilot-otel`), not a `.jsonl` file |
| `src/prevue/engines/usage.py:180-189` | `_parse_copilot_otel` calls `Path(otel_path).read_text()` — directory → `OSError` → `None` → `estimated=True` |
| `tests/test_reusable_workflow_yaml.py:360` | Fixture uses file path — doesn't catch workflow dir mismatch |

**Impact:** Copilot reviews in Actions still show `~est` tokens despite PERF-03 wiring.

**Fix:** Point env at concrete `.jsonl` file **or** teach parser to glob `path/*.jsonl` (+ optional `~/.copilot/otel/*.jsonl`).

---

### T-02 · Model precedence inverted vs `CONFIG_PRECEDENCE`
**Sources:** branch audit #2, code quality #3  
**Severity:** High (overlapping — treat as confirmed)

| Location | Issue |
|----------|-------|
| `src/prevue/config.py:12`, `CONFIG_PRECEDENCE` | Documents `PREVUE_MODEL env > COPILOT_MODEL env > engine.model in yml` |
| `src/prevue/config.py:241-257` | `_resolve_model()` implements correct ladder — **never called** from production |
| `src/prevue/review.py:808-809` | `_review_model = _review_model_from_config or _env_model` — **yml beats env** (inverted) |
| `tests/test_config_precedence.py` | Tests `_resolve_model` in isolation only — no integration test |

**Impact:** Consumer with `engine.model` in yml + `PREVUE_MODEL` in workflow → yml wins. Violates WKFL-05/D-07.

**Fix:** `_review_model = _env_model or _review_model_from_config`, or call `_resolve_model()` at review site. Add integration test.

---

### T-03 · Consumer doc sweep — Claude secret rename incomplete
**Sources:** branch audit #3  
**Severity:** Medium → **blocker for merge** (migration risk)

CR-01 fixed `configuration.md`, `consumer-setup.md`, `README.md`, `SECURITY.md`, `prevue-command-run.yml`.

**Still stale:**

| File | Lines (approx) | Stale content |
|------|----------------|---------------|
| `docs/GETTING-STARTED.md` | 24, 69, 79 | `ANTHROPIC_API_KEY`, `anthropic-api-key` |
| `docs/DEVELOPMENT.md` | 303, 427 | `SKELETON_ENGINES`, `ANTHROPIC_API_KEY` |
| `docs/TESTING.md` | 118, 344 | `ANTHROPIC_API_KEY`, `anthropic-api-key` |
| `docs/ARCHITECTURE.md` | 100 | `gemini-cli` / `GeminiAdapter` |

**Fix:** Replace with `claude-code-oauth-token` / `CLAUDE_CODE_OAUTH_TOKEN`. Update architecture for antigravity-cli `functional=False`.

---

## P1 — Correctness / devex (non-blocker but high signal)

### T-04 · Retry path under-reports real token usage
**Sources:** branch audit #5, code quality (flow.py retry accounting)

| Location | Issue |
|----------|-------|
| `src/prevue/engines/flow.py` (~1171-1175, `_retry_token_meta`) | `best_capture = captured_retry or captured` — one invocation only |
| Same area | Byte-estimate `review` sums both calls; `input`/`output`/`cost_usd` from one capture |

**Fix:** Sum captures when both exist, or document invariant + align sticky output.

---

### T-05 · Auth/engine hard-fail skips OUTP-05 machine output
**Sources:** branch audit #6

| Location | Issue |
|----------|-------|
| `src/prevue/review.py` | `emit_machine_output` only on skip/noop/success (lines 215, 463, 1313) |
| `src/prevue/cli.py:59-61` | `AuthError` → exit 1, no emit |

**Fix:** Emit failure-shaped compact output + artifact on `AuthError` / `NonFunctionalEngineError` before exit.

---

### T-06 · `GITHUB_OUTPUT` write failures silently dropped
**Sources:** branch audit #7

| Location | Issue |
|----------|-------|
| `src/prevue/review.py:1483-1484` | `except OSError: pass` on output write |

**Fix:** Log warning to stderr (match `PREVUE_RESULT_FILE` pattern).

---

### T-07 · Cursor/antigravity cost line omitted when usage capture returns None
**Sources:** `10-REVIEW.md` WR-02 (prior review, not re-flagged by thermos but still open)

| Location | Issue |
|----------|-------|
| `src/prevue/engines/flow.py:154-221` | `compute_cost` only when `capture_usage` succeeds |
| `src/prevue/github/comments.py:551-555` | Tokens shown, cost absent — inconsistent UX |

**Fix:** Feed bytes/4 estimate into `compute_cost` with `~est` label when real usage unavailable.

---

### T-08 · Claude `--bare` removal — CI determinism tradeoff
**Sources:** branch audit #4

| Location | Issue |
|----------|-------|
| `src/prevue/engines/spec.py:108-115` | Dropped `--bare` (blocks `CLAUDE_CODE_OAUTH_TOKEN`) |

**Fix:** Document tradeoff in SECURITY.md / consumer-setup. Re-evaluate if Claude adds OAuth + bare compat.

---

### T-09 · OTEL parser returns `estimated=False` on empty file
**Sources:** branch audit #9

| Location | Issue |
|----------|-------|
| `src/prevue/engines/usage.py:229-234` | Zero totals still `estimated: False` if path exists |

**Fix:** Treat empty/zero as `estimated=True` or omit usage block.

---

## P2 — Structural / maintainability (code quality pass)

Do **not** block merge if P0 fixed — schedule Phase 10.1 or early Phase 11 cleanup.

### Q-01 · Extract machine output from `review.py`
**Severity:** BLOCKER (maintainability)

| Location | Issue |
|----------|-------|
| `src/prevue/review.py:1316-1429` | `emit_machine_output`, `build_compact_output`, `build_full_output` (~115 lines) |
| File total | **1429 lines** (+176 vs main; already >1k rule) |

**Fix:** Extract `prevue/output.py` or `prevue/github/output.py`.

---

### Q-02 · Kill config dict round-trip at adapter wiring
**Severity:** High

| Location | Issue |
|----------|-------|
| `src/prevue/review.py:571-606` | `EngineConfig` → fake dict → `_resolve_engine_models()` re-parse |
| Same | `hasattr(engine, "set_raw_args")` duck-type |

**Fix:** `get_adapter(name, raw_args=..., pricing_override=...)` or `AdapterContext` at factory. `resolve_engine_models(engine_config: EngineConfig)` on `PrevueConfig`.

---

### Q-03 · Split `usage_capture` from stdout envelope format
**Severity:** High

| Location | Issue |
|----------|-------|
| `src/prevue/engines/spec.py:129-146` | Cursor forced into `usage_capture="stdout-json"` for fence unwrap only |
| `src/prevue/engines/flow.py:294` | `_resolve_fence_source` keys on `usage_capture` |

**Fix:** New spec axis: `stdout_format: "plain" | "json_envelope"` vs `usage_capture: "otel" | "envelope_usage" | "none"`.

---

### Q-04 · Antigravity TTY hack — name check in generic adapter
**Severity:** High

| Location | Issue |
|----------|-------|
| `src/prevue/engines/cli_adapter.py:170-197` | `if spec.name == "antigravity-cli"` — 40-line bash/script block |

**Fix:** Spec field: `invoke_wrapper` or `prompt_delivery: "argv-pty"`.

---

### Q-05 · Dedupe capture/cost orchestration in `flow.py`
**Severity:** Medium

| Location | Issue |
|----------|-------|
| `src/prevue/engines/flow.py:154-221` | Identical capture + `compute_cost` block for first invoke and retry |

**Fix:** `_enrich_capture(spec, stdout, model_label, pricing_override, otel_path) -> dict | None`.

---

### Q-06 · Table-drive `_invoke` argv builder
**Severity:** Medium

| Location | Issue |
|----------|-------|
| `src/prevue/engines/cli_adapter.py:104-206` | 120-line tri-branch; model-flag + raw_args repeated 3× |

**Fix:** `(delivery, model_flag) -> argv steps` table.

---

### Q-07 · Registry typing
**Severity:** Medium

| Location | Issue |
|----------|-------|
| `src/prevue/engines/registry.py:20,40,63` | `ENGINES: dict[str, object]` + `# type: ignore` |

**Fix:** `dict[str, CliEngineSpec]`.

---

### Q-08 · Shim debt — legacy adapter subclasses
**Severity:** Low

| Location | Issue |
|----------|-------|
| `src/prevue/engines/copilot_cli.py` (+ cursor, claude siblings) | Subclass stubs for test compat |

**Fix:** Migrate tests to `CliEngineAdapter` + spec fixtures; delete stubs.

---

## Pass / no action

| Area | Status |
|------|--------|
| `raw_args` list-only + base-ref gate | OK |
| Antigravity `functional=False` fail-closed | OK |
| Claude/Cursor JSON envelope fence unwrap | OK |
| Multi-call `cost_usd` aggregation in review | OK |
| Skip/noop machine output | OK |
| Inline comment fingerprint refresh (CR-03) | OK |
| `update-pricing.yml` supply chain | OK (mitigated by PR review gate) |

---

## Suggested fix order for Sonnet 4.6

```
1. T-01  OTEL path/parser          → verify: sandbox Copilot run, no ~est on tokens
2. T-02  model precedence          → verify: test_config_precedence integration test
3. T-03  doc sweep                 → verify: rg ANTHROPIC_API_KEY docs/ (excl .planning)
4. Commit CR-01 fixes (if not yet) → verify: test_security_md + workflow yaml tests
5. T-04  retry token sum           → verify: test_usage_capture or flow unit test
6. T-05/T-06  output on failure    → verify: test_output_contract.py
7. Q-01+  structural (optional)    → separate PR or 10.1 cleanup
```

---

## Test commands

```bash
uv run pytest -q
./scripts/ci-local.sh
uv run pytest tests/test_config_precedence.py tests/test_output_contract.py tests/test_usage_capture.py tests/test_reusable_workflow_yaml.py -q
rg 'ANTHROPIC_API_KEY|anthropic-api-key|gemini-cli' docs/ README.md SECURITY.md --glob '!**/.planning/**'
```

---

## Raw reviewer outputs

<details>
<summary>Branch audit summary</summary>

- High: OTEL dir-vs-file, model precedence inversion
- Medium: doc drift (partial CR-01), Claude --bare removal, retry under-count, auth skip emit, silent GITHUB_OUTPUT drop
- Low: gemini removal OK, empty OTEL estimated=False, pricing workflow hygiene

</details>

<details>
<summary>Code quality summary</summary>

- Blocker: review.py 1429 lines, output helpers misplaced
- High: config round-trip, unused _resolve_model, usage_capture conflation, antigravity name branch
- Medium: flow.py duplication, retry accounting, registry typing
- Good: CliEngineSpec consolidation, shared parse_envelope, raw_args validator, pricing module

</details>
