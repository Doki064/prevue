---
phase: 09-classification-skill-loading-multi-call-review
plan: "03"
subsystem: importscan
tags: [importscan, D-06, ENGN-06, TDD, security, cross-file, static-analysis]
dependency_graph:
  requires:
    - src/prevue/models.py (ChangedFile model)
    - tests/test_importscan.py (RED scaffold from 09-01)
  provides:
    - src/prevue/importscan.extract_imports
    - src/prevue/importscan.referenced_paths
    - src/prevue/importscan.KNOWN_LANGUAGES
  affects:
    - src/prevue/multicall.py (09-05 splitter consumes referenced_paths for co-location)
tech_stack:
  added: []
  patterns:
    - ast.parse parse-only (never eval/exec) for Python import extraction
    - tolerant regex fallback for partial/unparseable Python hunks
    - regex-only for JS/TS specifier extraction
    - broad try/except T-09-09 degrade-to-empty per file
    - V12 path containment: filter out absolute and traversal candidates
key_files:
  created:
    - src/prevue/importscan.py
  modified: []
decisions:
  - "referenced_paths(path, patch) two-arg signature matches 09-01 RED scaffold contract (not list[ChangedFile] as described in plan behavior section)"
  - "Relative JS specifier resolution uses os.path.normpath for safe path joining; only relative specifiers (./  ../) produce candidates"
  - "Python ast-first path: SyntaxError on partial hunks falls through to tolerant regex — no loss on incomplete diff fragments (Pitfall 6)"
  - "KNOWN_LANGUAGES exported for downstream dispatch consumers"
metrics:
  duration: "4 min"
  completed: "2026-06-21T17:12:52Z"
  tasks: 3
  files: 1
---

# Phase 09 Plan 03: Safe Cross-File Import Scan (D-06) Summary

stdlib ast + regex import scanner that extracts Python and JS/TS references from patch added-lines, degrades gracefully on garbage/unknown input, and never executes code (T-09-08/V5/V12).

## What Was Built

### Task 1: RED (verified pre-existing scaffold)

The RED scaffold was created in Plan 09-01 (commit 83431c0) and confirmed failing with `ImportError: No module named 'prevue.importscan'`. The 12-test scaffold covers:

- `TestExtractImports`: 7 tests (Python stdlib import, from-import, JS import, require, removed-lines exclusion, empty patch, unparseable degrade)
- `TestReferencedPaths`: 5 tests (relative Python, relative JS, absolute package filter, empty patch, unparseable degrade)

### Task 2: GREEN — `src/prevue/importscan.py` (commit 9e8573e)

**`extract_imports(path, patch) -> list[str]`**

Extension dispatch:
- `.py`/`.pyi` → `_extract_python_imports`: ast.parse mode="exec" first; SyntaxError/Exception falls to `_PY_IMPORT_RE` regex (`^\s*(?:import|from)\s+([\w.]+)`)
- `.js/.jsx/.ts/.tsx/.mjs/.cjs` → `_extract_js_imports`: three regexes covering ES `import/export from`, CJS `require()`, and dynamic `import()`
- Everything else → `[]` (degrade, D-06 discretion)

**`referenced_paths(path, patch) -> set[str]`**

Calls `extract_imports`, then for each specifier:
- Python: relative (leading `.`) resolves via level-based directory walk + `module.replace(".", "/")` + `.py`/`__init__.py` candidates; absolute dotted modules generate truncated path candidates
- JS/TS: relative-only (`./` or `../`); `os.path.normpath(join(importer_dir, spec))` + extension candidates
- V12 containment: filters out any candidate starting with `/` or containing `..` path segments

**`KNOWN_LANGUAGES`** — frozenset of all dispatched extensions, exported for downstream.

**`_added_lines(patch)`** — strips `+++` metadata and leading `+` from each diff line.

Security invariants (T-09-08):
- `ast.parse` is parse-only — no `eval`/`exec`/`compile`-and-run
- All regex operations are read-only (`re` module)
- No `subprocess`, no `os.system`
- Every per-file scan in `extract_imports`/`referenced_paths` wrapped in `try/except Exception` → degrade to `[]`/`set()`

### Task 3: REFACTOR (commit 241265d)

Removed unused `_PY_EXTENSIONS_FOR_RESOLVE` constant. Confirmed degrade invariants are centralized in the public API wrappers.

## Verification

```
uv run pytest tests/test_importscan.py -x -q
# → 12 passed

uv run ruff check src/prevue/importscan.py
# → All checks passed

uv run pytest -q
# → 18 failed (test_multicall.py RED scaffold only), 671 passed

grep -n "exec\|eval\|os.system\|subprocess" src/prevue/importscan.py
# → Only comments and ast.parse(source, mode="exec") — no executing calls
```

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED  | 83431c0 (09-01) | PASS — tests failed with ImportError as expected |
| GREEN | 9e8573e | PASS — 12/12 tests green |
| REFACTOR | 241265d | PASS — tests still green after cleanup |

## Deviations from Plan

**1. [Rule 1 - Signature] referenced_paths uses (path, patch) not (files)**
- **Found during:** GREEN implementation
- **Issue:** Plan `<behavior>` described `referenced_paths(files)` taking a `list[ChangedFile]`, but the 09-01 RED scaffold (which pins the API contract) uses `referenced_paths("src/api/users.py", patch)` — two string arguments
- **Fix:** Implemented the two-arg signature matching the test contract. The splitter (09-05) will call extract_imports/referenced_paths per file and build the cross-file mapping itself
- **Files modified:** `src/prevue/importscan.py`
- **Commit:** 9e8573e

## Known Stubs

None — full implementation, no hardcoded empty returns.

## Threat Flags

No new threat surface introduced beyond what is documented in the plan's `<threat_model>`. T-09-08 (parse-never-exec) and T-09-10 (V12 path containment) mitigations are implemented as specified.

## Self-Check

- [x] `src/prevue/importscan.py` exists and exports `extract_imports`, `referenced_paths` — FOUND
- [x] GREEN commit 9e8573e exists — FOUND
- [x] REFACTOR commit 241265d exists — FOUND
- [x] `uv run pytest tests/test_importscan.py -q` → 12 passed — VERIFIED
- [x] `uv run ruff check src/prevue/importscan.py` → clean — VERIFIED
- [x] No exec/eval/os.system/subprocess executing calls in importscan.py — VERIFIED

## Self-Check: PASSED
