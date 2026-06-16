---
phase: 8
slug: incremental-stateful-review-lifecycle
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-15
audited: 2026-06-16
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `08-RESEARCH.md` §Validation Architecture. Retroactive audit
> completed 2026-06-16 after full phase execution (plans 08-01..08-10).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-cov 7.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest -q` |
| **Full suite command** | `uv run pytest --cov=src/prevue` |
| **Estimated runtime** | ~3 seconds (479 tests; GitHub API mocked via `responses`) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q`
- **After every plan wave:** Run `uv run pytest --cov=src/prevue`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | LIFE-02 | T-08-fingerprint | Deterministic `sha(path\|normalize(title))`; line/severity/suggestion excluded | unit | `uv run pytest tests/test_fingerprint.py -q` | ✅ | ✅ green |
| 08-01-02 | 01 | 1 | LIFE-02 | — | `normalize(title)` unicode-stable (NFKC, casefold, punct strip) | unit | `uv run pytest tests/test_fingerprint.py -k normalize -q` | ✅ | ✅ green |
| 08-01-03 | 01 | 1 | LIFE-01/04 | — | Compare + GraphQL JSON fixtures valid for downstream mocks | fixture | `uv run python -c "import json,glob; [json.load(open(p)) for p in glob.glob('tests/fixtures/compare_*.json')+glob.glob('tests/fixtures/graphql_*.json')]"` | ✅ | ✅ green |
| 08-02-01 | 02 | 1 | LIFE-02 | — | Severity parse-back: inverse of `SEVERITY_BADGES` round-trips | unit | `uv run pytest tests/test_comments.py -k severity_parse -q` | ✅ | ✅ green |
| 08-02-02 | 02 | 1 | LIFE-04 | — | Hunk-overlap `finding_region_changed` heuristic | unit | `uv run pytest tests/test_positions.py -k region -q` | ✅ | ✅ green |
| 08-03-01 | 03 | 2 | LIFE-01 | — | Marker SHA parse/write round-trip; legacy head-less → None | unit | `uv run pytest tests/test_comments.py -k marker_sha -q` | ✅ | ✅ green |
| 08-03-02 | 03 | 2 | LIFE-01 | — | `decide_scope`: incremental / full / noop / diverged fallback | unit | `uv run pytest tests/test_diff.py -k scope -q` | ✅ | ✅ green |
| 08-03-03 | 03 | 2 | LIFE-02 | T-08-gate | `apply_gate` over open-set blocks false-green | unit | `uv run pytest tests/test_gate.py -k open_set -q` | ✅ | ✅ green |
| 08-03-04 | 03 | 2 | LIFE-01/02/04 | — | Config knobs `incremental` / `resolve_outdated` / `max_known_issues` | unit | `uv run pytest tests/test_gate.py tests/test_config.py -k "knob or incremental or max_known" -q` | ✅ | ✅ green |
| 08-04-01 | 04 | 2 | LIFE-04 | — | GraphQL thread fetch + resolve; 403 best-effort skip | unit | `uv run pytest tests/test_graphql.py -q` | ✅ | ✅ green |
| 08-04-02 | 04 | 2 | LIFE-02 | SECR-02 | Known-issues list fenced UNTRUSTED DATA in prompt | unit | `uv run pytest tests/test_prompt.py -k known_issues -q` | ✅ | ✅ green |
| 08-05-01 | 05 | 3 | LIFE-02 | — | Carry-forward: out-of-scope priors untouched | integration | `uv run pytest tests/test_comments.py -k carry_forward -q` | ✅ | ✅ green |
| 08-05-02 | 05 | 3 | LIFE-02 | — | Escalation-only inline edit; equal severity skip | integration | `uv run pytest tests/test_comments.py -k escalation -q` | ✅ | ✅ green |
| 08-05-03 | 05 | 3 | LIFE-04 | — | Outdated resolve: in-scope + region-changed + fingerprint absent | integration | `uv run pytest tests/test_comments.py -k outdated -q` | ✅ | ✅ green |
| 08-05-04 | 05 | 3 | LIFE-02 | — | `derive_prior_findings` re-derives from live comments | integration | `uv run pytest tests/test_comments.py -k prior_finding -q` | ✅ | ✅ green |
| 08-06-01 | 06 | 3 | LIFE-01 | — | `run_review` scope seam: full / incremental / noop | integration | `uv run pytest tests/test_review_flow.py -k "incremental or noop or scope" -q` | ✅ | ✅ green |
| 08-06-02 | 06 | 3 | LIFE-01/02/04 | — | Open-set gate, known-issues cap, force-push fallback, resolve opt-out | integration | `uv run pytest tests/test_review_flow.py -k "open_set or known_issues or force_push or resolve_opt_out" -q` | ✅ | ✅ green |
| 08-07-01 | 07 | 4 | LIFE-01/04 | WKFL-04 | Reusable workflow permissions minimal + docs knobs | yaml | `uv run pytest tests/test_reusable_workflow_yaml.py -q` | ✅ | ✅ green |
| 08-08-01 | 08 | 5 | LIFE-02 | T-08-08 | Open-set keeps carried title on rephrase-at-same-line | integration | `uv run pytest tests/test_review_flow.py::test_open_set_dedupes_carried_prior_at_same_line_as_current -q` | ✅ | ✅ green |
| 08-08-02 | 08 | 5 | LIFE-02 | — | True duplicate at same line drops prior (current wins) | integration | `uv run pytest tests/test_review_flow.py::test_open_set_drops_true_duplicate_at_same_line -q` | ✅ | ✅ green |
| 08-08-03 | 08 | 5 | LIFE-02 | — | Inline skip-edit on rephrase-at-same-line (no escalation) | integration | `uv run pytest tests/test_comments.py -k rephrase_at_same_line -q` | ✅ | ✅ green |
| 08-09-01 | 09 | 5 | LIFE-02 | T-08-09 | GFM `INLINE_MARKER`; legacy `<sub>` still detected | unit | `uv run pytest tests/test_comments.py -k "marker or legacy_sub" -q` | ✅ | ✅ green |
| 08-09-02 | 09 | 5 | LIFE-02 | — | Incremental scope disclaimer in sticky Review section | unit | `uv run pytest tests/test_comments.py -k disclaimer -q` | ✅ | ✅ green |
| 08-10-01 | 10 | 5 | LIFE-01 | — | cursor-cli `cwd=PREVUE_CONSUMER_ROOT` isolation | contract | `uv run pytest tests/test_engine_contract.py -k "cwd or consumer" -q` | ✅ | ✅ green |
| 08-10-02 | 10 | 5 | LIFE-01 | — | Preflight noop skips engine CLI install | yaml | `uv run pytest tests/test_workflow_yaml.py -k preflight -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_fingerprint.py` — fingerprint + normalize pure units (08-01)
- [x] `tests/fixtures/compare_*.json` — REST compare API mocks (08-01)
- [x] `tests/fixtures/graphql_*.json` — GraphQL thread/resolve/403 mocks (08-01)
- [x] Reuse existing `conftest.py` fixtures (PrContext, fake PR/comment payloads)

*Existing pytest + `responses` infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `resolveReviewThread` token scope on live GitHub | LIFE-04 | GitHub does not document exact scope; 403 behavior verified unit-side but live scope needs sandbox runner | Sandbox PR with only `pull-requests: write`; trigger outdated finding; confirm resolve 200 vs 403-skip path. UAT test 6 pass on PR #23/#24. |
| Incremental scoping across real second push | LIFE-01 | End-to-end SHA-marker round-trip is integration on live PR | Push once (full), push again touching one file; confirm in-scope-only re-review + marker advance. UAT tests 1–2, 9 pass on PR #24. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-16

---

## Validation Audit 2026-06-16

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Tasks mapped | 24 |
| Automated (green) | 24 |
| Manual-only | 2 |
| Full suite | 479 passed |

**Audit notes:** State A — existing VALIDATION.md was draft from planning (all rows pending). Cross-reference against executed plans 08-01..08-10 and live test files confirmed full Nyquist coverage. No new tests generated; no implementation changes required.
