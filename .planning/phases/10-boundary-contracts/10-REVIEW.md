---
phase: 10-boundary-contracts
reviewed: 2026-07-01T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/prevue/engines/usage.py
  - src/prevue/engines/spec.py
  - src/prevue/engines/cli_adapter.py
  - .github/workflows/prevue-review.yml
  - .github/workflows/prevue-command-run.yml
  - tests/test_usage_capture.py
  - tests/test_reusable_workflow_yaml.py
  - tests/fixtures/usage/copilot_otel.jsonl
  - docs/configuration.md
findings:
  critical: 2
  warning: 2
  info: 1
  total: 5
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-07-01
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

This change rewrites `usage.py::_parse_copilot_otel` for the real Copilot CLI flat-span OTEL JSONL schema, flips `copilot-cli`'s `usage_capture` back to `"otel-jsonl"`, wires `COPILOT_OTEL_FILE_EXPORTER_PATH` into both reusable workflow entry points, and updates fixtures/tests/docs to match (commits `2a75168`, `60daa3e`). The parser rewrite itself is a real improvement over the previous fictitious `resourceSpans`/`scopeSpans` OTLP-shape parser, and the retry/accumulation logic in `flow.py` (`_merge_retry_tokens` / `otel_accumulates`) correctly avoids double-counting OTEL spans across a retried invocation.

However, the entire justification for this gap-closure — "the real Copilot CLI file exporter writes flat span-per-line records with `gen_ai.usage.*` keys" — was root-caused against a **locally installed `gh copilot` v1.0.67**, while `.github/scripts/install-engine-cli.sh` (not touched by either commit in this change set) still pins CI to `@github/copilot@1.0.61`. Nothing in this change verifies, bumps, or even flags that pin in a way that would surface a mismatch. This matters because the *previous* gap-closure round concluded OTEL export was "inert" on that exact pinned version (`1.0.61`) — the very conclusion this change calls "stale" — yet the stale-conclusion evidence and this fix's evidence were gathered against two different CLI versions, and the CI-pinned version was never re-verified. `docs/configuration.md` even hedges this explicitly ("verify against the pinned install version") rather than resolving it. Additionally, the new flat-span parser has a real aggregation bug: a malformed numeric field partway through one span's `attributes` dict causes the rest of that span's fields to be silently dropped while fields already summed earlier in the same span are kept, and `span_count` is incremented regardless — producing a corrupted, non-zero-but-wrong total that is still reported as `estimated=False` ("trustworthy, real data"). This directly contradicts the function's own stated design goal of never returning a misleading `estimated=False` result when no real usage data exists.

## Structural Findings (fallow)

None provided for this review invocation.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Fix root-caused against gh copilot v1.0.67, but CI still installs 1.0.61 — unverified against the actual deployment environment

**File:** `.github/scripts/install-engine-cli.sh:8` (not modified by this change), cross-referenced with `src/prevue/engines/spec.py:114-127`, `src/prevue/engines/usage.py:15-16,194-196`, `docs/configuration.md:298,306`

**Issue:** The entire premise of this gap-closure plan — that the real Copilot CLI OTEL file exporter writes flat `{"type": "span"|"metric", "attributes": {...}}` records with `gen_ai.usage.*` keys — was diagnosed by installing `gh copilot` **v1.0.67** locally (per the `spec.py` comment, the `usage.py` docstring, and the 10-09 planning docs, all of which explicitly cite "v1.0.67"). But `install-engine-cli.sh`, the script that actually provisions the Copilot CLI inside the two reusable workflows this same change touches, still pins:

```bash
npm install -g @github/copilot@1.0.61
```

This script was **not modified** by either commit in this change set (`2a75168` "rewrite _parse_copilot_otel", `60daa3e` "flip to otel-jsonl and wire OTEL export path"). The *prior* (10-08) gap-closure round had concluded `COPILOT_OTEL_FILE_EXPORTER_PATH` was "inert" specifically on `1.0.61` — that conclusion is exactly what this change calls "stale" and reverses, but the reversal's supporting evidence comes from a different, newer CLI version than the one CI actually runs. `docs/configuration.md:298` (added by this change) states: "confirmed present in `@github/copilot` v1.0.67+; verify against the pinned install version in 'Engine install versions' below" — this is a direct admission that the verification gap exists, and it is left unresolved within the same change (line 306's table still reads `1.0.61`, unchanged).

Net effect: this fix may not work at all in the actual GitHub Actions environment it targets — the flat-span schema may differ, or OTEL export may still be unavailable, on `1.0.61` — and there is no test, CI check, or version-pin bump that would catch a mismatch. `10-VERIFICATION.md`'s `human_verification` entry says a live CI spot-check "remains an open follow-up," but that follow-up is framed as confirming the fix works end-to-end, not as reconciling the version discrepancy that makes the outcome uncertain in the first place. Given prior history in this exact code path (a previous "confirmed inert" conclusion was itself wrong), shipping a second unverified version-dependent claim without closing the loop is a real risk of landing a no-op fix a second time.

**Fix:** Either bump `install-engine-cli.sh`'s pin to `1.0.67` (or a later, confirmed-compatible version) as part of this same change, or explicitly re-verify the flat-span schema against `1.0.61` before flipping `usage_capture` back to `"otel-jsonl"`. At minimum, add a runtime diagnostic: when `_parse_copilot_otel` returns `None` for a copilot-cli run where `COPILOT_OTEL_FILE_EXPORTER_PATH` is set and the path exists (i.e. "we looked, but found nothing usable"), emit a stderr note with the first line's top-level keys, so a version/schema mismatch is visible in CI logs instead of silently degrading to `estimated=True` with zero diagnostic signal.

### CR-02: Partial-field parse failure inside one OTEL span silently produces a corrupted total reported as `estimated=False` (trustworthy) instead of degrading cleanly

**File:** `src/prevue/engines/usage.py:279-286`

**Issue:**

```python
span_count += 1
try:
    total_input += int(attrs.get(_OTEL_INPUT_TOKENS, 0) or 0)
    total_output += int(attrs.get(_OTEL_OUTPUT_TOKENS, 0) or 0)
    total_cache_read += int(attrs.get(_OTEL_CACHE_READ_TOKENS, 0) or 0)
    total_cache_creation += int(attrs.get(_OTEL_CACHE_CREATION_TOKENS, 0) or 0)
except (TypeError, ValueError):
    continue  # skip malformed span (T-10-07)
```

All four token fields for one span are summed inside a single `try` block, and `span_count += 1` happens *before* the block runs. If one field (e.g. `gen_ai.usage.output_tokens`) is malformed (non-numeric) while an earlier field on the same line (`gen_ai.usage.input_tokens`) is valid, the earlier field's increment is **not rolled back** when the exception fires on the later field. Verified directly against the current code:

```python
>>> _parse_copilot_otel(<file with one span: input_tokens=500, output_tokens="garbage">)
{'input': 500, 'output': 0, 'cache_read': 0, 'cache_creation': 0, 'estimated': False}
```

and, worse — if the *first* field parsed (`input_tokens`) is the malformed one, `span_count` was already incremented before the exception, so the function still returns a non-`None` result instead of degrading:

```python
>>> _parse_copilot_otel(<file with one span: input_tokens="garbage", output_tokens=10>)
{'input': 0, 'output': 0, 'cache_read': 0, 'cache_creation': 0, 'estimated': False}
```

This is exactly the failure mode the function's own docstring says it avoids — the `span_count == 0` guard's comment (lines 292-297) states the intent is to avoid "reporting a misleading estimated=False zeroed dict," but that guard only protects the file-level "zero real spans seen" case; it does not protect against a single malformed field silently zeroing (or partially zeroing) an otherwise-real span while still being counted as "real" (`estimated=False`). A caller (the sticky PR comment / cost report) will display this corrupted total as trustworthy real token data. `tests/test_usage_capture.py` has no test combining one valid field with one malformed field on the same span, so this gap is unguarded.

**Fix:** Parse all four fields into local variables first, without mutating the running totals; only merge into the totals (and increment `span_count`) if the entire span parses cleanly. Otherwise skip the whole span, same as any other malformed-span case:

```python
parsed: dict[str, int] = {}
span_ok = True
for key, field in (
    ("input", _OTEL_INPUT_TOKENS),
    ("output", _OTEL_OUTPUT_TOKENS),
    ("cache_read", _OTEL_CACHE_READ_TOKENS),
    ("cache_creation", _OTEL_CACHE_CREATION_TOKENS),
):
    try:
        parsed[key] = int(attrs.get(field, 0) or 0)
    except (TypeError, ValueError):
        span_ok = False
        break
if not span_ok:
    continue  # malformed span — do not count toward span_count or totals
span_count += 1
total_input += parsed["input"]
total_output += parsed["output"]
total_cache_read += parsed["cache_read"]
total_cache_creation += parsed["cache_creation"]
```

## Warnings

### WR-01: `docs/configuration.md`'s new OTEL claim hedges rather than resolves the version-mismatch gap it documents

**File:** `docs/configuration.md:298,306`

**Issue:** Line 298 (added by this change) reads: "confirmed present in `@github/copilot` v1.0.67+; verify against the pinned install version in 'Engine install versions' below." Line 306 (pre-existing, unchanged by this change) shows `copilot-cli` pinned at `1.0.61` in that same table. This documents the ambiguity from CR-01 rather than resolving it — a consumer reading this doc still has to cross-reference two places and comes away unsure whether real-token capture actually works on the version their CI will install, which is exactly the opposite of what a "boundary contracts" phase's docs should guarantee.

**Fix:** Once CR-01 is resolved (pin bumped or `1.0.61` re-verified), update line 298 to state plainly whether the pinned version supports OTEL export and the flat-span schema, rather than instructing the reader to self-verify.

### WR-02: `span_count`'s doc comment claims a stronger guarantee than the code currently provides

**File:** `src/prevue/engines/usage.py:250-251,279`

**Issue:** The comment at lines 250-251 states `span_count` "distinguishes 'no real spans found' from a genuine zero-token span" — implying `span_count > 0` means at least one span's tokens were actually captured. As shown in CR-02, `span_count` is incremented as soon as a record passes the `type == "span"` / `isinstance(attrs, dict)` shape checks, before any token field is parsed — so the comment's guarantee does not currently hold for partially-malformed spans.

**Fix:** This will be resolved as a byproduct of the CR-02 fix (only increment `span_count` for spans that fully parsed). Until then, the comment overstates what the guard actually protects against.

## Info

### IN-01: `github.copilot.cost` is correctly excluded from the parsed result, but no regression test pins that decision

**File:** `src/prevue/engines/usage.py:212-214`

**Issue:** The docstring explains `github.copilot.cost` is deliberately not read here, to keep a single cost-computation path via `pricing.compute_cost` (documented as T-10-09-02, a tampering mitigation — an exporter-supplied cost value shouldn't be trusted as-is). This is a sound design decision, but no test in `tests/test_usage_capture.py` asserts a span carrying a suspicious `github.copilot.cost` value doesn't leak into the returned dict's `cost_usd` (which is computed downstream by `flow._enrich_capture`, not by `_parse_copilot_otel` itself). A future refactor could silently reintroduce a direct read of this field without any test catching the regression.

**Fix:** Add a small regression test: a span fixture with `"github.copilot.cost": 999999.0` alongside valid `gen_ai.usage.*` fields, asserting `_parse_copilot_otel`'s returned dict has no `cost_usd` key (that field is only ever added later, by `flow._enrich_capture`/`pricing.compute_cost`).

---

_Reviewed: 2026-07-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
