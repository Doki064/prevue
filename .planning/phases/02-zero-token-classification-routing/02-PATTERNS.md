# Phase 2: Zero-Token Classification & Routing - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 11 (7 new, 4 modified)
**Analogs found:** 11 / 11 (Phase 1 walking skeleton supplies a strong analog for every file)

## File Classification

| New/Modified File | New/Mod | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|---------|------|-----------|----------------|---------------|
| `src/prevue/classify/models.py` (`Rule`, `RuleSet`, `ClassificationResult`) | new | model | transform | `src/prevue/models.py` | exact (pydantic model module) |
| `src/prevue/classify/rules.py` (`load_default_rules`, `load_ruleset`, `merge_rules`) | new | config | file-I/O | `src/prevue/github/client.py` (`load_pr_context` — read+parse+validate) | role-match (config loader) |
| `src/prevue/classify/default_rules.yml` | new | config (data) | n/a | none (no data file in repo) | no analog — see below |
| `src/prevue/classify/filter.py` (`filter_diff`) | new | service | transform | `src/prevue/github/diff.py` (`fetch_diff` — produces `DiffBundle`) | role-match (pure transform over `DiffBundle`) |
| `src/prevue/classify/classifier.py` (`classify`) | new | service | transform | `src/prevue/engines/base.py` + `diff.py` pure-fn style | role-match (pure `(in)->(out)`) |
| `src/prevue/classify/router.py` (`route`) | new | service | transform | `classifier.py` (sibling pure fn) | role-match |
| `src/prevue/classify/__init__.py` | new | package | n/a | `src/prevue/github/__init__.py` | exact |
| `src/prevue/review.py` (insert stage, D-10 skip) | modified | orchestration | request-response | itself — `run_review()` | exact (extend in place) |
| `src/prevue/github/comments.py` (`render_body` Metadata, skip note) | modified | presentation | transform | itself — `render_body` | exact (extend in place) |
| `tests/test_classify_*.py` (filter/classifier/rules/router) | new | test | n/a | `tests/test_models.py` (table-driven, no mocks) | exact (pure-fn unit style) |
| `tests/test_review_flow.py` + `tests/test_comments.py` | modified | test | n/a | themselves | exact (extend, `patch()` style) |

## Pattern Assignments

### `src/prevue/classify/models.py` (model, transform)

**Analog:** `src/prevue/models.py` (read in full, lines 1-45)

Match the exact module conventions Phase 1 locked: module docstring, `from __future__ import annotations`, `from pydantic import BaseModel, Field`, PEP 604 unions (`str | None`), `Field(default_factory=...)` for mutable defaults, inline `#` comments documenting decisions.

**Imports + model pattern** (`models.py` lines 1-21):
```python
"""Engine adapter contract — typed data shape for fetch → engine → post."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChangedFile(BaseModel):
    path: str
    status: str  # added | modified | removed | renamed
    additions: int
    deletions: int
    patch: str | None = None  # unified-diff hunks; None when GitHub omits (large/binary)


class DiffBundle(BaseModel):
    pr_number: int
    base_sha: str
    head_sha: str
    files: list[ChangedFile]
```

**Default-factory pattern for collection fields** (`models.py` lines 41-44) — use for `ClassificationResult.labels`/`bundles`:
```python
class ReviewResult(BaseModel):
    summary_markdown: str
    findings: list[Finding] = Field(default_factory=list)
    engine_meta: dict = Field(default_factory=dict)
```

**Recommended new models** (per RESEARCH Open Question 1 — separate `ClassificationResult`, keep `DiffBundle` a pure diff shape):
```python
class ClassificationResult(BaseModel):
    labels: dict[str, str] = Field(default_factory=dict)  # label -> matched glob (audit, D-09)
    bundles: list[str] = Field(default_factory=list)      # bundle identifiers (ROUT-01)
    dropped_count: int = 0                                # filtered files (D-09/D-10)

class RuleSet(BaseModel):
    ignore_globs: list[str] = Field(default_factory=list)
    label_rules: dict[str, list[str]] = Field(default_factory=dict)
    routing_map: dict[str, str] = Field(default_factory=dict)
```

---

### `src/prevue/classify/rules.py` (config, file-I/O)

**Analog:** `src/prevue/github/client.py` (read full, lines 1-38) — the "read a source, parse it, return a validated typed object" pattern.

**Read + parse + return-typed pattern** (`client.py` lines 21-32):
```python
def load_pr_context() -> PrContext:
    """Read PR context from GITHUB_EVENT_PATH + GITHUB_REPOSITORY in one parse."""
    repo_full = os.environ["GITHUB_REPOSITORY"]
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
    pr = event["pull_request"]
    return PrContext(...)
```
Mirror this for YAML: one parse, return a validated `RuleSet`. Per RESEARCH Pattern 3, load packaged defaults via `importlib.resources.files("prevue.classify") / "default_rules.yml"` (NOT `__file__`), parse with `yaml.safe_load` (NEVER `yaml.load`), then `RuleSet.model_validate(...)`. Consumer `.github/prevue.yml` is optional in Phase 2 (RESEARCH Open Question 2) and read from the trusted base ref only.

---

### `src/prevue/classify/filter.py` (service, transform)

**Analog:** `src/prevue/github/diff.py` (read full, lines 1-28) — pure function producing a `DiffBundle`.

**Module + DiffBundle-construction pattern** (`diff.py` lines 1-7, 23-28):
```python
"""Fetch PR diff via GitHub REST API (no checkout)."""

from __future__ import annotations

from prevue.github.client import get_authenticated_pull, load_pr_context
from prevue.models import ChangedFile, DiffBundle
...
    return DiffBundle(pr_number=ctx.pr_number, base_sha=pr.base.sha, head_sha=pr.head.sha, files=files)
```
For the filter, produce a NEW reduced bundle via `diff.model_copy(update={"files": kept})` (RESEARCH Pattern 1 / anti-pattern: never mutate in place). Signature `filter_diff(diff, ignore_globs) -> tuple[DiffBundle, list[ChangedFile]]` using `GitIgnoreSpec.from_lines(ignore_globs).match_file(f.path)`.

---

### `src/prevue/classify/classifier.py` (service, transform)

**Analog:** pure-function style of `diff.py` + the port discipline of `engines/base.py`. No I/O, no mocks.

Use **one `GitIgnoreSpec` per label** with `spec.check_file(path)` → `CheckResult(file, include, index)`; `label_rules[label][res.index]` is the matched glob for the audit trail (RESEARCH Pattern 2). PR-level `general` fallback only when the real-label union is empty (D-03; RESEARCH Pitfall 3). Sort labels in a fixed canonical order before returning (RESEARCH Pitfall 5).

---

### `src/prevue/classify/router.py` (service, transform)

**Analog:** `classifier.py` sibling — same pure-fn module shape. `route(labels, routing_map) -> list[str]`: consumer map entry wins, else 1:1 by name (D-06). Emits identifier strings only. Sort output for determinism.

---

### `src/prevue/review.py` (orchestration, request-response) — MODIFIED

**Analog:** itself — extend `run_review()` (read full, lines 1-50).

**Existing seam to insert into** (`review.py` lines 30-49):
```python
def run_review(*, adapter: EngineAdapter | None = None) -> None:
    ctx = load_pr_context()
    if ctx.head_repo_full != ctx.base_repo_full:
        raise ForkPrUnsupported()
    diff = fetch_diff()
    req = ReviewRequest(diff=diff, instructions=BASELINE_INSTRUCTIONS,
                        budget_seconds=300, model=os.environ.get("COPILOT_MODEL"))
    engine = adapter or CopilotCliAdapter()
    result = engine.review(req)
    pr = get_authenticated_pull(ctx)
    upsert_sticky(pr, result)
```
Insert between `fetch_diff()` and building `req`: `load_ruleset()` → `filter_diff()` (D-08) → **D-10 skip branch** (`if not reduced.files: upsert_skip_note(...); return` — gate BEFORE the engine, RESEARCH Pitfall 4 filter-first ordering) → `classify()` → `route()`, then pass `diff=reduced` into `ReviewRequest` and thread the `ClassificationResult` to `upsert_sticky`. Keep the existing `ForkPrUnsupported` guard ordering. Note: new imports must be top-of-file like the existing `from prevue.github.diff import fetch_diff`.

**Module-level constant + custom-exception pattern** (`review.py` lines 14-27) for any new constants (e.g. canonical label order):
```python
BASELINE_INSTRUCTIONS = (...)

class ForkPrUnsupported(Exception):
    def __init__(self) -> None:
        super().__init__(FORK_UNSUPPORTED_MSG)
```

---

### `src/prevue/github/comments.py` (presentation, transform) — MODIFIED

**Analog:** itself — extend `render_body` (read full, lines 1-44).

**Existing Metadata placeholder to fill** (`comments.py` lines 11-22):
```python
def render_body(result: ReviewResult) -> str:
    """Sectioned sticky body: Verdict / Review / Metadata (D-04, D-05)."""
    model = result.engine_meta.get("model", "unknown")
    duration = result.engine_meta.get("duration_s", "?")
    return (
        f"{MARKER}\n"
        "## Prevue Review\n\n"
        "### Verdict\n..."
        f"### Metadata\nEngine: copilot-cli · model: {model} · {duration}s\n"
    )
```
D-09: extend the `### Metadata` section to render labels + matched rule per label (compact, not per-file). `render_body` must accept the optional `ClassificationResult`. Add a separate `upsert_skip_note(pr, dropped_count)` for D-10, reusing the existing `MARKER` + `upsert_sticky` upsert mechanics (`comments.py` lines 36-43) so the skip note is also sticky/idempotent. Sort labels in canonical order before rendering (RESEARCH Pitfall 5).

---

### `tests/test_classify_*.py` (test, new — Wave 0)

**Analog:** `tests/test_models.py` (read full) — table-driven, pure, zero mocks. This is the exact style for filter/classifier/rules/router tests (RESEARCH: "table-driven `(paths, ruleset) → expected labels` with zero mocking").

**Parametrized table pattern** (`test_models.py` lines 68-71):
```python
@pytest.mark.parametrize("model_cls", [DiffBundle, ReviewRequest])
def test_no_pr_title_or_body_fields(model_cls: type) -> None:
    ...
```
**Plain-literal fixture builder pattern** (`test_review_flow.py` lines 29-43) — build `ChangedFile`/`DiffBundle` from literals, no I/O:
```python
def _sample_diff() -> DiffBundle:
    return DiffBundle(pr_number=PR_NUMBER, base_sha=BASE_SHA, head_sha=HEAD_SHA,
        files=[ChangedFile(path="src/example.py", status="modified",
                           additions=3, deletions=1, patch="@@ -1 +1 @@\n-old\n+new")])
```
For the packaged-resource test, assert `importlib.resources.files("prevue.classify") / "default_rules.yml"` resolves and `yaml.safe_load`s into a valid `RuleSet` (RESEARCH A2 wheel-inclusion trap).

---

### `tests/test_review_flow.py` + `tests/test_comments.py` (test, modified)

**Analog:** themselves. Use the established `patch(...)` context-manager block to stub the orchestration seam.

**Patch-block + capture pattern** (`test_review_flow.py` lines 66-85):
```python
with (
    patch("prevue.review.load_pr_context", return_value=_sample_ctx()),
    patch("prevue.review.fetch_diff", return_value=sample_diff) as mock_fetch,
    patch("prevue.review.get_authenticated_pull", return_value=mock_pr),
    patch("prevue.review.upsert_sticky") as mock_upsert,
):
    run_review(adapter=fake_engine)
```
Extend with: (1) `-k filtered` — engine receives reduced bundle (capture `req.diff.files`, assert noise absent, D-08); (2) `-k empty_skip` — all-filtered PR calls the skip note and NEVER the engine (`mock_upsert`/engine not called). For comments, add `-k metadata` asserting labels + matched globs render in the Metadata section, following the existing `render_body` assertion style (`test_comments.py` lines 25-37).

---

## Shared Patterns

### Module header convention
**Source:** every module — e.g. `src/prevue/models.py` lines 1-5
**Apply to:** all new `classify/*.py` files
```python
"""<one-line module purpose>."""

from __future__ import annotations
```

### Pydantic at every system boundary
**Source:** `src/prevue/models.py` (whole file)
**Apply to:** `classify/models.py`, `rules.py` (validate parsed YAML into `RuleSet`)
PEP 604 unions, `Field(default_factory=...)` for mutable defaults, inline `#` decision comments. RESEARCH: validate config at the boundary, fail-closed (Phase 1 D-09) on malformed rules.

### Read-from-trusted-source + safe-parse
**Source:** `src/prevue/github/client.py` lines 21-32 (`json.load`) → mirror with `yaml.safe_load`
**Apply to:** `rules.py`
Always `yaml.safe_load`, never `yaml.load`. Consumer `prevue.yml` from trusted base ref only (V4/V5 ASVS; SECR-01/WKFL-03).

### Pure-transform, never mutate input
**Source:** `diff.py` builds a fresh `DiffBundle`; pydantic `model_copy(update=...)`
**Apply to:** `filter.py`, `classifier.py`, `router.py`
No I/O, no in-place mutation — keeps tests mock-free and the "zero token" guarantee structural.

### Sticky-comment upsert mechanics
**Source:** `src/prevue/github/comments.py` lines 7-8, 36-43 (`MARKER`, `upsert_sticky`)
**Apply to:** new `upsert_skip_note` (D-10) — reuse marker + upsert loop for idempotent skip note.

### Test style: pure unit, table-driven, patch-the-seam
**Source:** `tests/test_models.py` (pure), `tests/test_review_flow.py` lines 66-99 (`patch` block)
**Apply to:** all Wave 0 + extended tests. Pure functions need data fixtures only; orchestration tests patch `prevue.review.*` names.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/prevue/classify/default_rules.yml` | config (data) | n/a | No YAML/data file exists in the repo yet. Use RESEARCH Code Examples §default rules for shape (`ignore`/`labels`/`routing` keys). Must ship in the wheel — verify with `importlib.resources` packaging test (RESEARCH A2). |

Note: `pyproject.toml` must add `pathspec==1.1.*` and `PyYAML==6.0.*` (not yet declared) — first plan task. Existing deps: `pydantic==2.13.*`, `pygithub==2.9.*`.

## Metadata

**Analog search scope:** `src/prevue/`, `src/prevue/github/`, `src/prevue/engines/`, `tests/`
**Files scanned:** 8 source files + 4 test files + pyproject.toml (all read in full; non-overlapping)
**Pattern extraction date:** 2026-06-11
