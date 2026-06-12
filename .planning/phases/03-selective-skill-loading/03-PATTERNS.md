# Phase 3: Selective Skill Loading - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 9 (4 new code/model + 1 new package data tree + 4 test files [2 new, 2 extended])
**Analogs found:** 9 / 9 (every seam has a strong in-repo analog — this phase is composition, not invention)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/prevue/skills/loader.py` (NEW) | service/loader | file-I/O + transform | `src/prevue/classify/rules.py` (packaged-data load) + `src/prevue/classify/classifier.py` (pathspec select) + `src/prevue/classify/router.py` (dedupe+order) | exact (composite) |
| `src/prevue/skills/models.py` (NEW) | model | transform | `src/prevue/classify/models.py` (`RuleSet`/`ClassificationResult` pydantic) + `src/prevue/models.py` (`ReviewRequest`) | exact |
| `src/prevue/skills/<bundle>/<skill>.md` × ~12 (NEW data) | config/data | static resource | `src/prevue/classify/default_rules.yml` (glob-authoring style + packaged-resource convention) | exact |
| `src/prevue/skills/__init__.py` + per-bundle `__init__.py` (NEW) | package marker | n/a | `src/prevue/classify/__init__.py` | exact |
| `src/prevue/review.py` (MODIFIED) | controller/orchestration | request-response | itself (`run_review()` seam, lines 50-64) | self |
| `src/prevue/github/comments.py` (MODIFIED) | view/render | transform | itself (`render_body`/`upsert_sticky`, lines 19-104) | self |
| `tests/test_skills_loader.py` (NEW) | test | n/a | `tests/test_review_flow.py` (patch/capture style) | role-match |
| `tests/test_skills_builtin.py` (NEW) | test | n/a | `tests/test_comments.py` (render assertions) | role-match |
| `tests/test_review_flow.py` (MODIFIED) | test | n/a | itself | self |
| `tests/test_comments.py` (MODIFIED) | test | n/a | itself | self |
| `pyproject.toml` (MODIFIED) | config | n/a | existing `[project].dependencies` | self |

> Note: `src/prevue/models.py` is NOT modified — `ReviewRequest.instructions` (models.py:24-28) is already the injection target; the loader produces the string, review.py passes it.

---

## Pattern Assignments

### `src/prevue/skills/loader.py` (loader, file-I/O + transform)

This file is a composite of three existing analogs. Copy each sub-pattern from its owner.

**Analog 1 — Packaged-data load (`src/prevue/classify/rules.py`)**

`rules.py:13-16` is the exact SKIL-04-by-construction pattern (D-10). It uses `importlib.resources.files(...)` over a single file; the loader generalizes it to a tree iteration:

```python
# rules.py lines 13-16
def load_default_rules() -> dict:
    """Read default_rules.yml via importlib.resources — never __file__ (A2)."""
    resource = importlib.resources.files("prevue.classify") / "default_rules.yml"
    return yaml.safe_load(resource.read_text(encoding="utf-8"))
```

Loader generalization (RESEARCH Pattern 1): `importlib.resources.files("prevue.skills")`, `iterdir()` over bundle dirs (skip non-dirs and `__pycache__`), then `entry.read_text(encoding="utf-8")` per `.md`. **Use `frontmatter.loads(text)` not `frontmatter.load(path)`** — `Traversable` is not a guaranteed real filesystem path (RESEARCH Pattern 1 note + Anti-Pattern).

**Analog 2 — pathspec per-skill selection (`src/prevue/classify/classifier.py`)**

`classifier.py:36-46` builds one `GitIgnoreSpec` per label and matches files. Reuse `GitIgnoreSpec.from_lines(...)` verbatim — D-05 forbids re-implementing glob matching:

```python
# classifier.py lines 36-46
specs = {
    label: GitIgnoreSpec.from_lines(globs)
    for label, globs in label_rules.items()
}
for f in files:
    for label, spec in specs.items():
        if label in labels:
            continue
        res = spec.check_file(f.path)
        if res.include:
            labels[label] = label_rules[label][res.index]
```

Loader difference: classifier wants *which glob* matched (`res.index`) for provenance; D-13 surfaces skill **names** not globs, so the simpler boolean `any(spec.match_file(p) for p in paths)` suffices (RESEARCH Pattern 2).

**Analog 3 — dedupe + canonical order (`src/prevue/classify/router.py`)**

`router.py:8-26` is the exact dedupe (seen-set → append) and canonical-order pattern to mirror for D-09 + D-08:

```python
# router.py lines 8-26
def _canonical_index(label: str) -> int:
    try:
        return CANONICAL_LABEL_ORDER.index(label)
    except ValueError:
        return len(CANONICAL_LABEL_ORDER)

def route(labels: list[str], routing_map: dict[str, str]) -> list[str]:
    ordered = sorted(labels, key=_canonical_index)
    bundles: list[str] = []
    seen: set[str] = set()
    for label in ordered:
        bundle = routing_map.get(label, label)
        if bundle in seen:
            continue
        seen.add(bundle)
        bundles.append(bundle)
    return bundles
```

Loader applies the same `_canonical_index` fallback-to-end semantics on `skill.bundle`, dedupes by `f"{bundle}/{filename}"`, then `matched.sort(key=lambda s: (_rank(s.bundle), s.filename))` (D-08: bundle rank, then filename-alpha). **This is the THIRD copy of `_canonical_index`** (router.py:8, comments.py:12) — see Shared Patterns / Open Question 3: prefer lifting a shared `canonical_index()` into `classify/models.py`.

**Context assembly (D-07):** `"\n\n".join([baseline] + [f"## Skill: {s.name}\n{s.body.strip()}" for s in skills])`; return bare `baseline` when `skills` is empty (D-06). No analog — new, but trivial (RESEARCH Pattern 4).

---

### `src/prevue/skills/models.py` (model, transform)

**Analog:** `src/prevue/classify/models.py` (lines 18-31) — every system-boundary shape is a pydantic `BaseModel`.

```python
# classify/models.py lines 18-23 — the model style to mirror
class RuleSet(BaseModel):
    """Built-in + consumer classification rules (D-04, ROUT-01)."""
    ignore_globs: list[str] = Field(default_factory=list)
    label_rules: dict[str, list[str]] = Field(default_factory=dict)
    routing_map: dict[str, str] = Field(default_factory=dict)
```

**Fail-closed validation (D-12)** is established by `rules.py:48-85` calling `RuleSet.model_validate(...)` and letting it raise. The `Skill` model adds two things this repo hasn't used yet but RESEARCH specifies (Pitfalls 1 + 3):
- `applies_to: list[str] = Field(alias="applies-to", min_length=1)` — hyphenated YAML key → underscore field via alias; `min_length=1` makes empty/missing globs raise.
- `model_config = ConfigDict(populate_by_name=True)`.
- Loader-populated (not from frontmatter): `bundle`, `filename`, `body` defaulting to `""`.

Validate via `Skill.model_validate(post.metadata)` — same `model_validate` call style as `rules.py`.

---

### `src/prevue/skills/<bundle>/<skill>.md` (data, static resource)

**Analog:** `src/prevue/classify/default_rules.yml` (lines 22-47) — the authoritative glob-authoring style the skill `applies-to` globs must mirror (Pitfall 4: gitignore anchoring). Use `**/*.py`, `terraform/**`, `.github/workflows/**`, `**/.env*` — never bare `*.py`.

The 5 bundles + ~12 skill files (incl. MANDATORY `security/committed-secrets.md`, D-11) are fully drafted in RESEARCH "Skill Content Drafts" (frontmatter + body per file). The structure, the security-secrets requirement, and the glob style are load-bearing; body wording is tunable (RESEARCH A2). Bundle directory names MUST be the canonical bundle ids (`security`, `frontend`, `backend`, `data`, `infra`) so `_canonical_index(bundle)` resolves (D-08).

**Packaging guard (Pitfall 2 / A1):** `default_rules.yml` already proves nested non-`.py` data ships inside `prevue.classify` via `uv_build`. Add a test asserting ≥1 `.md` is readable through `importlib.resources.files("prevue.skills")` after install; `uv sync` after adding files.

---

### `src/prevue/review.py` (orchestration, MODIFIED)

**Analog:** itself. Insert between `route()` (line 51) and `ReviewRequest` construction (line 54-59). Current state:

```python
# review.py lines 50-59 — the exact seam
result_cls = classify(reduced.files, ruleset.label_rules)
result_cls.bundles = route(list(result_cls.labels.keys()), ruleset.routing_map)
result_cls.dropped_count = len(dropped)

req = ReviewRequest(
    diff=reduced,
    instructions=BASELINE_INSTRUCTIONS,   # ← replace with assembled instructions
    budget_seconds=300,
    model=os.environ.get("COPILOT_MODEL"),
)
```

Changes (RESEARCH integration example):
- New import: `from prevue.skills.loader import assemble_instructions, load_skills, select_skills`.
- After line 52: `skills = load_skills()` (raises on bad frontmatter, D-12); `matched = select_skills(skills, [f.path for f in reduced.files])`; `instructions = assemble_instructions(BASELINE_INSTRUCTIONS, matched)`.
- Line 56: `instructions=instructions` (D-06/D-07). `BASELINE_INSTRUCTIONS` (lines 18-22) stays as the preamble constant.
- Line 64: `upsert_sticky(pr, result, classification=result_cls, loaded_skills=[f"{s.name} ({s.bundle})" for s in matched])` (D-13).

`load_skills()` is called inside `run_review`, so its raise (D-12) propagates exactly like `EngineFailure` already does — and `test_engine_failure_propagates_without_upsert` (test_review_flow.py:182) is the proof pattern that a raise pre-upsert skips the sticky.

---

### `src/prevue/github/comments.py` (render, MODIFIED)

**Analog:** itself — `render_body` (lines 19-59) + `upsert_sticky` (lines 96-104) already accept an optional keyword-only `classification` and append to the `metadata` string. D-13 mirrors that exactly:

```python
# comments.py lines 19-27 + 44-49 — the keyword-only-optional + metadata-append pattern
def render_body(result, *, classification=None) -> str:
    ...
    metadata = f"Engine: copilot-cli · model: {model} · {duration}s"
    if classification is not None:
        ...
        if classification.bundles:
            bundles_line = ", ".join(sorted(classification.bundles, key=_canonical_index))
            metadata += f"\nBundles: {bundles_line}"
```

Add a `loaded_skills: list[str] | None = None` keyword-only param to both `render_body` and `upsert_sticky`; append `metadata += "\nSkills: " + ", ".join(loaded_skills)` (else `"\nSkills: none (baseline only)"` when classification present — RESEARCH A5, makes D-06 auditable). Default `None` keeps existing call sites + tests green.

---

### `tests/test_skills_loader.py` (NEW)

**Analog:** `tests/test_review_flow.py` — copy the `patch(...)` + capture-dict idiom (lines 53-89) and the `pytest.raises` idiom (lines 182-194) for the D-12 fail-closed cases. Use a `tests/fixtures/skills/` tree or tmp dir (RESEARCH Wave 0 conftest gap) so selection/order/dedupe tests don't couple to real built-in content. Covers SKIL-01 (backend-only selects backend+security not frontend/data/infra), D-06/D-08/D-09, D-12 (`pytest.raises` on missing/empty `applies-to`), SKIL-04 (load path is packaged dir).

### `tests/test_skills_builtin.py` (NEW)

**Analog:** `tests/test_comments.py` (lines 19-52) — plain assertion style over real artifacts. Covers SKIL-02 (5 bundle dirs exist, every built-in skill parses+validates, `committed-secrets` present) and the `importlib.resources` packaging-readable guard (Pitfall 2).

### `tests/test_review_flow.py` (MODIFIED)

**BEHAVIOR CHANGE — not a regression.** Line 87 currently asserts `req.instructions == BASELINE_INSTRUCTIONS` on a `src/example.py` (backend) PR. After Phase 3 a `.py` PR matches backend+security skills, so `instructions` will no longer equal the bare baseline. Update to assert the baseline is a *prefix* / `## Skill:` sections present, and add a `loaded_skills` kwarg assertion on `upsert_sticky` (D-13). The capture idiom (lines 58-64) already exposes `req.instructions`.

### `tests/test_comments.py` (MODIFIED)

Add `test_render_body_loaded_skills`: pass `loaded_skills=[...]`, assert a `Skills:` line renders (mirror `test_render_body_metadata_shows_labels_and_matched_globs`, lines 41-51).

---

## Shared Patterns

### Packaged-data / trusted-ref load (SKIL-04, D-10)
**Source:** `src/prevue/classify/rules.py` lines 13-16
**Apply to:** `skills/loader.py`
`importlib.resources.files("prevue.skills")` + `read_text(encoding="utf-8")`. Never `__file__`, never the PR head. This is the SKIL-04-by-construction mechanism — assert/test the load path is the framework dir.

### pathspec glob matching (D-03/D-05)
**Source:** `src/prevue/classify/classifier.py` lines 5, 36-46 (`from pathspec import GitIgnoreSpec`; `GitIgnoreSpec.from_lines(globs)`)
**Apply to:** `skills/loader.py` `select_skills`. Reuse verbatim — re-implementing glob matching violates D-05.

### Canonical order + dedupe (D-08/D-09)
**Source:** `src/prevue/classify/router.py` lines 8-26 (and the duplicate `_canonical_index` at `comments.py:12`)
**Apply to:** `skills/loader.py`. **Open Question 3 (RESEARCH):** this would be the THIRD copy of `_canonical_index`. Prefer lifting a single `canonical_index(name)` helper into `classify/models.py` next to `CANONICAL_LABEL_ORDER` and importing it in router.py, comments.py, and loader.py — aligns with D-05 "reuse at helper level." Planner's call.

### Fail-closed pydantic validation (D-12)
**Source:** `src/prevue/classify/rules.py` lines 48-85 + `classify/models.py` lines 18-31
**Apply to:** `skills/models.py` `Skill` + the `Skill.model_validate(post.metadata)` call in the loader. Mirrors Phase 1 D-09 / Phase 2 fail-closed posture: validate on load, let pydantic raise, never silently skip.

### Optional keyword-only audit threading (D-13)
**Source:** `src/prevue/github/comments.py` lines 19-27, 96-104 (the `*, classification=None` + `metadata += ...` shape)
**Apply to:** `loaded_skills=None` param on `render_body`/`upsert_sticky`, threaded from `run_review`. Default-None keeps existing tests green.

---

## No Analog Found

None. Every seam this phase needs already exists in the repo. The only genuinely new elements are:

| Element | Why no analog needed |
|---------|----------------------|
| Context assembly string (`## Skill:` join, D-07) | Trivial f-string join; RESEARCH Pattern 4 is the full spec |
| `Field(alias="applies-to")` + `min_length=1` | New pydantic feature usage for this repo, but standard pydantic v2 (RESEARCH Pitfall 1) |
| `python-frontmatter` dependency | New dep — **gate `uv add python-frontmatter==1.3.*` behind `checkpoint:human-verify`** per RESEARCH legitimacy audit (SUS verdict, likely false-positive) |

## Metadata

**Analog search scope:** `src/prevue/classify/` (rules, models, router, classifier, filter, default_rules.yml), `src/prevue/review.py`, `src/prevue/models.py`, `src/prevue/github/comments.py`, `tests/` (test_review_flow, test_comments)
**Files scanned:** 9 source/test files read in full + RESEARCH/CONTEXT
**Pattern extraction date:** 2026-06-12
