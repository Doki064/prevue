---
phase: 02-zero-token-classification-routing
reviewed: 2026-06-12T12:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/prevue/classify/__init__.py
  - src/prevue/classify/default_rules.yml
  - src/prevue/classify/models.py
  - src/prevue/classify/rules.py
  - src/prevue/classify/filter.py
  - src/prevue/classify/classifier.py
  - src/prevue/classify/router.py
  - src/prevue/review.py
  - src/prevue/github/comments.py
findings:
  critical: 0
  warning: 4
  info: 2
  total: 6
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-06-12T12:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the Phase 2 zero-token classification pipeline: rule loading/merge, filter, classify, route, orchestration in `run_review`, and sticky-comment Metadata/skip rendering. Core design is sound — pure transforms, `yaml.safe_load`, fail-closed consumer validation, filter-first D-10 gate, no subprocess/network in classify package.

No security vulnerabilities or crash-level logic bugs found. Four warnings: Metadata bundle ordering breaks under partial custom routing (Pitfall 5 regression), empty PRs conflated with all-filtered skip, silent missing consumer config path, and duplicate bundle IDs when labels map to the same bundle. Two info items on duplicated helpers and unwired `consumer_path`.

## Warnings

### WR-01: Metadata bundle order wrong with partial routing overrides

**File:** `src/prevue/github/comments.py:37-39`
**Issue:** `render_body` re-sorts `classification.bundles` with `_canonical_index`, which indexes **label names** in `CANONICAL_LABEL_ORDER`, not bundle IDs. `route()` already emits bundles in canonical label order. When `routing_map` overrides some labels (e.g. `security → sec-bundle`) but leaves others 1:1 (e.g. `frontend`), custom bundle IDs get index `len(CANONICAL_LABEL_ORDER)` while default label-named bundles get real indices — sort permutes away from canonical label order. Violates Pitfall 5 / D-09 stable audit trail.
**Fix:** Drop the re-sort; `route()` output is already ordered.

```python
bundles_line = ", ".join(classification.bundles)
```

Add a test with `routing_map={"security": "sec-custom"}` and labels `{security, frontend}` — expect `sec-custom, frontend`, not `frontend, sec-custom`.

### WR-02: Zero-file PR conflated with all-filtered D-10 skip

**File:** `src/prevue/review.py:46-48`
**Issue:** `if not reduced.files` fires for both (a) all files dropped by ignore globs (D-10 intent) and (b) PRs with zero changed files (`fetch_diff` returns empty `files`, `dropped_count=0`). Case (b) posts `no reviewable files (0 filtered)`, which misstates D-10 — nothing was filtered. D-10 contract (02-CONTEXT) covers lockfile-only / all-noise PRs, not empty diffs.
**Fix:** Branch on whether filtering occurred:

```python
if not reduced.files:
    if dropped:
        upsert_skip_note(pr, dropped_count=len(dropped))
    else:
        upsert_skip_note(pr, dropped_count=0)  # or separate empty-PR message
    return
```

Or gate D-10 on `dropped and not reduced.files` and handle `not diff.files` separately.

### WR-03: Missing consumer config path fails silently

**File:** `src/prevue/classify/rules.py:57-58`
**Issue:** When `consumer_path` is set but `Path(consumer_path).is_file()` is false (typo, wrong cwd, not yet fetched from base ref), `load_ruleset` returns built-ins with no warning. Misconfiguration surfaces only as unexpected classification — hard to debug in consumer repos once Phase 5 wires the path.
**Fix:** Log or raise when `consumer_path` is non-`None` and file absent (configurable strict mode). At minimum document; prefer explicit error for production wiring.

### WR-04: Duplicate bundle IDs when labels map to same bundle

**File:** `src/prevue/classify/router.py:15-18`
**Issue:** `route` maps each label independently with no deduplication. Consumer routing like `{frontend: fullstack, backend: fullstack}` yields `["fullstack", "fullstack"]`. Phase 3 skill loading will receive duplicates unless downstream dedupes — risks double-loaded skills and inflated token use.
**Fix:** Deduplicate while preserving first-seen (canonical) order:

```python
seen: set[str] = set()
out: list[str] = []
for label in ordered:
    bundle = routing_map.get(label, label)
    if bundle not in seen:
        seen.add(bundle)
        out.append(bundle)
return out
```

---

## Info

### IN-01: Duplicated `_canonical_index` helper

**File:** `src/prevue/classify/router.py:8-12`, `src/prevue/github/comments.py:12-16`
**Issue:** Identical helper in two modules. Drift risk if canonical order changes in one place only.
**Fix:** Move to `models.py` next to `CANONICAL_LABEL_ORDER` (already dependency-free) and import in both.

### IN-02: `consumer_path` not wired in orchestration

**File:** `src/prevue/review.py:42`
**Issue:** `load_ruleset()` always called with default `None`. Parameter exists and is tested via fixtures but production path never passes consumer config — expected Phase 5 stub, not a defect today.
**Fix:** None until Phase 5; track in phase handoff.

---

_Reviewed: 2026-06-12T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
