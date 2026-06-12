# Phase 3: Selective Skill Loading - Research

**Researched:** 2026-06-12
**Domain:** Deterministic skill loader (SKILL.md frontmatter parsing + per-skill glob selection + context assembly), layered on Phase 2's pathspec classifier
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Bundle = directory of single-skill markdown files. Layout `src/prevue/skills/<bundle>/<skill>.md` (e.g. `skills/backend/error-handling.md`). One skill per file. Rejected: monolithic SKILL.md per bundle; single rules-style data file.
- **D-02:** Skill frontmatter = `name` + `description` + `applies-to` (globs). No `label`/bundle key in skill frontmatter — the bundle is the directory; routing semantics live in Phase 2's `routing_map`.
- **D-03:** Per-skill deterministic selection via `applies-to` globs, reusing Phase 2's pathspec engine. A skill loads only when the PR's changed-file paths match its globs — across any bundle.
- **D-04:** Skill globs are the primary load selector; bundles organize + carry audit/override semantics, NOT a load gate. Loader scans all skill files and loads any whose globs match — regardless of which bundles Phase 2 routed. Rejected: two-stage bundle-gate-then-skill-filter.
- **D-05:** Phase 3 layers on Phase 2; it does NOT revise or override it. The planner reuses Phase 2's pathspec helper (DRY at the helper level, no duplicated logic).
- **D-06:** No skill's globs match → fall back to `BASELINE_INSTRUCTIONS` alone. This is Phase 3's realization of Phase 2's `general` seam. No 6th `general` bundle (SKIL-02 lists only 5).
- **D-07:** Baseline preamble + delimited skill sections. `BASELINE_INSTRUCTIONS` stays as a short reviewer-role preamble; each matched skill body appended under a clear delimiter/header (e.g. `## Skill: <name>`).
- **D-08:** Deterministic skill order: Phase 2 `CANONICAL_LABEL_ORDER` of the skill's bundle (security→frontend→backend→data→infra), then filename alphabetically. Rejected: filesystem match order; per-skill `priority` key.
- **D-09:** Dedupe loaded skills by file path — each skill loads at most once even if multiple of its globs match. Mirrors Phase 2 router dedupe (WR-02).
- **D-10:** SKIL-04 satisfied by construction; assert the invariant, defer the machinery. Load only from the fixed framework `skills/` dir, add a test/assert that the load path is the framework dir, document the invariant. Real base-ref git resolution deferred to Phase 5/6.
- **D-11:** Real but lean checklists. Each bundle ships a handful of genuine review-guidance skills. **Security bundle MUST include a skill that flags secrets/credentials committed in the diff — alert, not redact.**
- **D-12:** Fail-closed on malformed/missing skill frontmatter. Validate all skill frontmatter on load and raise so CI/tests catch it; never silently skip.
- **D-13:** Surface loaded skill names + their bundles in the sticky-comment Metadata, extending the Phase 2 D-09 section.

### Claude's Discretion
- Loader module layout/path; exact frontmatter parser (STACK recommends **python-frontmatter 1.3.0**; planner should honor unless a better fit emerges).
- Exact delimiter/templating string for assembled skill sections (D-07 fixes the shape, not the literal markup).
- The actual default skill content per bundle (D-11 fixes depth + the security secrets requirement; researcher may draft from review best practices — drafts provided below).
- Whether skill frontmatter validation is a pydantic model vs manual check (D-12 fixes fail-closed behavior, not mechanism).

### Deferred Ideas (OUT OF SCOPE)
- Consumer custom skills + built-in override via `.github/prevue/skills/` (→ Phase 6, SKIL-03).
- Real trusted-base-ref git resolution (→ Phase 5/6).
- LLM upgrade of the no-match/`general` seam (→ Phase 5, CLSF-02).
- Token-budget packing + loaded-vs-skipped token transparency (→ Phase 6).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SKIL-01 | Skill loader loads only the matched skill bundles into the review context (SKILL.md-style markdown with routing metadata) | Per-skill `applies-to` glob match via reused `GitIgnoreSpec` (D-03/D-05); see Architecture Pattern 2 + the `select_skills()` seam. Delivers finer-than-floor precision: loads individual matched skills, not whole bundles. |
| SKIL-02 | Framework ships built-in skill bundles: security, frontend, backend, data, infra | Five-directory layout under `src/prevue/skills/` (D-01); drafted skill content + `applies-to` globs for all five bundles in the **Skill Content Drafts** section. Security bundle includes the mandatory `committed-secrets.md` skill. |
| SKIL-04 | Skills loaded from the trusted base ref only; PR-modified skill files never executed in same run | Satisfied by construction (D-10): load path is the packaged framework dir resolved via `importlib.resources.files("prevue.skills")` — never `__file__`, never the PR head. Invariant asserted + tested. See **Security Domain** + Pattern 4. |
</phase_requirements>

## Summary

Phase 3 inserts a **skill loader** into the existing `run_review()` orchestration, between Phase 2's `route()` call and the construction of `ReviewRequest`. The loader: (1) scans the packaged framework `skills/<bundle>/<skill>.md` tree, (2) parses each file's frontmatter with **python-frontmatter 1.3.0** (`frontmatter.load(path)` → `.metadata` dict + `.content` body), (3) validates frontmatter fail-closed via a pydantic model (raises on missing `name`/`description`/`applies-to`, D-12), (4) selects per-skill by matching the PR's already-filtered changed-file paths against each skill's `applies-to` globs using the **same `GitIgnoreSpec` engine Phase 2 uses** (D-03/D-05), (5) dedupes by file path (D-09), (6) orders by the skill's bundle position in `CANONICAL_LABEL_ORDER` then filename-alpha (D-08), and (7) assembles `BASELINE_INSTRUCTIONS` preamble + `## Skill: <name>` delimited sections into `ReviewRequest.instructions` (D-07). When zero skills match, instructions fall back to `BASELINE_INSTRUCTIONS` alone (D-06). Loaded skill names + bundles thread into `upsert_sticky()` Metadata (D-13).

Every dependency and seam this phase needs **already exists** in the repo: `GitIgnoreSpec` (reuse from `filter.py`/`classifier.py`), `CANONICAL_LABEL_ORDER` (`classify/models.py`), the `route()` dedupe pattern, the `render_body()` Metadata renderer, and `importlib.resources.files()` packaged-data loading (exactly the pattern `rules.py` uses for `default_rules.yml`). The only **new** dependency is `python-frontmatter==1.3.*`, which must be added to `pyproject.toml` (currently absent — `pathspec`, `pydantic`, `pygithub`, `pyyaml` are present; `python-frontmatter` and `unidiff` from STACK.md are not yet installed).

**Primary recommendation:** Build a new `prevue.skills` package (loader module `prevue/skills/loader.py` + a `Skill` pydantic model + the five skill-content directories). Load the tree via `importlib.resources.files("prevue.skills")` — mirroring `rules.py` — to satisfy SKIL-04 by construction. Reuse `GitIgnoreSpec.from_lines(applies_to)` per skill; do not re-implement glob matching. Slot `select_skills()` + `assemble_instructions()` into `run_review()` right after the `route()` line, replacing the hardcoded `instructions=BASELINE_INSTRUCTIONS` argument.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Scan + parse skill files | Loader (new `prevue.skills`) | — | New responsibility; packaged-data read like `rules.py` |
| Validate skill frontmatter (fail-closed) | Loader / pydantic `Skill` model | — | System-boundary validation = pydantic (established Phase 1/2 pattern) |
| Per-skill glob selection | Loader, reusing `classify` pathspec | `classify` (helper owner) | D-05: reuse `GitIgnoreSpec`; do not duplicate |
| Deterministic ordering | Loader, reading `CANONICAL_LABEL_ORDER` | `classify/models.py` (constant owner) | D-08; constant already lives in models.py |
| Context assembly (preamble + sections) | Loader | `review.py` (orchestration) | D-07; produces the `instructions` string |
| No-match fallback | `review.py` orchestration | Loader (returns empty → review.py picks baseline) | D-06; orchestration owns the seam, same as Phase 2 |
| Audit surfacing (loaded skills) | `github/comments.py` `render_body()` | Loader (supplies the list) | D-13; presentation never imports the loader's internals |
| Trusted-ref invariant | Loader (`importlib.resources`) | test/assert | SKIL-04 by construction (D-10) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-frontmatter | 1.3.0 | Parse SKILL.md YAML frontmatter + markdown body | `frontmatter.load(path)` returns `.metadata` (dict) + `.content` (body) in one call; uses `yaml.SafeLoader` by default. The de-facto Python frontmatter parser; STACK.md-mandated. `[VERIFIED: PyPI metadata — name=python-frontmatter, version=1.3.0, requires_python>=3.10, uploaded 2026-05-20]` `[CITED: python-frontmatter.readthedocs.io]` |
| pathspec (`GitIgnoreSpec`) | 1.1.1 | Per-skill `applies-to` glob matching | **Already installed + used by Phase 2.** Reuse — do not add or re-implement. `[VERIFIED: executed `pathspec.__version__` == 1.1.1 in repo venv]` |
| pydantic | 2.13.4 | `Skill` model for fail-closed frontmatter validation (D-12) | **Already installed.** Every system-boundary shape is a pydantic model (Phase 1/2 locked it). `[VERIFIED: executed `pydantic.VERSION` == 2.13.4 in repo venv]` |
| PyYAML | 6.0.3 | Transitive dep of python-frontmatter (its YAML backend) | **Already installed.** python-frontmatter ≥1.3 calls `yaml.load(..., Loader=SafeLoader)`. Don't add a second YAML lib. `[CITED: github.com/eyeseast/python-frontmatter default_handlers.py — `kwargs.setdefault("Loader", SafeLoader)`]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| importlib.resources (stdlib) | — | Resolve the packaged `skills/` tree (`files("prevue.skills")`) | Loader path resolution — **mirror `rules.py`'s `importlib.resources.files("prevue.classify")` pattern** (T-A2: never `__file__`). Satisfies SKIL-04 by construction. `[VERIFIED: repo grep — rules.py uses this pattern]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-frontmatter | Hand-roll `---\n...\n---` split + `yaml.safe_load` | STACK.md "What NOT to Use": never invent a custom skill format. python-frontmatter handles edge cases (no frontmatter, empty body, BOM) and keeps Agent-Skills portability. Reject hand-roll. |
| pydantic `Skill` model | Manual `if "applies-to" not in meta: raise` | D-12 allows either. pydantic is the established pattern (Phase 1/2), gives a typed object downstream, and frees-form-error messages CI surfaces. **Recommend pydantic** for consistency. |
| Reuse `GitIgnoreSpec` | New per-skill matcher | D-05 forbids duplication. Reuse is mandatory. |

**Installation:**
```bash
uv add python-frontmatter==1.3.*
```
(adds to `pyproject.toml` `[project].dependencies`; `pathspec`, `pydantic`, `pyyaml` already present.)

**Version verification:**
- `python-frontmatter` `1.3.0` — confirmed live at `https://pypi.org/pypi/python-frontmatter/json` (uploaded 2026-05-20, `requires_python >=3.10`). `[VERIFIED: PyPI registry]`
- `pathspec 1.1.1`, `pydantic 2.13.4` — confirmed by executing `__version__` inside the repo's uv venv. `[VERIFIED: repo venv]`

## Package Legitimacy Audit

> One new package this phase: `python-frontmatter`. Run before install.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| python-frontmatter | PyPI | 1.3.0 published 2026-05-20 (project itself is years old — eyeseast/python-frontmatter) | unknown (seam returned null) | github.com/eyeseast/python-frontmatter (exposed in PyPI `project_urls.repository`) | **SUS** (seam) | **Flagged — planner adds `checkpoint:human-verify` before `uv add`** |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** `python-frontmatter`.

**Verdict context (important — likely false-positive):** The legitimacy seam flagged `python-frontmatter` SUS for `too-new`, `unknown-downloads`, `no-repository`. These are **metadata-parsing artifacts, not genuine risk signals**:
- `too-new` reflects the **1.3.0 release date** (2026-05-20), not package age. python-frontmatter is a long-established project (maintainer eyeseast, on PyPI for years).
- `no-repository` is a seam gap: PyPI metadata **does** expose `project_urls.repository = https://github.com/eyeseast/python-frontmatter` and `documentation = python-frontmatter.rtfd.io` — confirmed live. `[VERIFIED: PyPI JSON]`
- `unknown-downloads` — the seam couldn't fetch the downloads stat; not evidence of low usage.
- This package is **explicitly recommended in STACK.md** (HIGH confidence, verified at source) and is the standard Python frontmatter parser.

Per protocol the SUS verdict still stands and the planner **must** add a `checkpoint:human-verify` task before `uv add python-frontmatter`. The human verifier should confirm: (1) the package is `eyeseast/python-frontmatter`, (2) version `1.3.*`, (3) no postinstall (PyPI wheels have no install scripts). Recommended human-verify command: `uv pip show python-frontmatter` after install + spot-check `github.com/eyeseast/python-frontmatter`.

## Architecture Patterns

### System Architecture Diagram

```
                 run_review()  (review.py — single orchestration seam)
                       │
   load_pr_context ──► fork guard ──► fetch_diff() ──► load_ruleset()
                       │
                       ▼
              filter_diff(diff, ignore_globs)  ──►  (reduced diff, dropped[])
                       │
            reduced.files empty? ──yes──► upsert_skip_note() ─► return  (D-10, unchanged)
                       │ no
                       ▼
              classify(reduced.files, label_rules) ─► ClassificationResult.labels
                       │
              route(labels, routing_map) ─► result_cls.bundles      (Phase 2, unchanged)
                       │
       ┌───────────────┴──────────── NEW IN PHASE 3 ───────────────────────┐
       ▼                                                                    │
  load_skills()                                                            │
   scan importlib.resources.files("prevue.skills")/<bundle>/<skill>.md     │
       │  frontmatter.load(path) → .metadata + .content                    │
       │  Skill.model_validate(meta)  ── fail-closed on bad frontmatter ──►raise (D-12)
       ▼                                                                    │
  select_skills(skills, reduced.files)                                     │
   per skill: GitIgnoreSpec.from_lines(skill.applies_to).match any path?   │ (D-03/D-05)
       │  dedupe by file path (seen-set)                                   │ (D-09)
       │  sort by (CANONICAL_LABEL_ORDER.index(bundle), filename)          │ (D-08)
       ▼                                                                    │
  matched skills empty? ──yes──► instructions = BASELINE_INSTRUCTIONS ─────┤ (D-06)
       │ no                                                                 │
       ▼                                                                    │
  assemble_instructions(BASELINE_INSTRUCTIONS, matched)                    │
   preamble + "\n\n## Skill: <name>\n<body>" per skill                     │ (D-07)
       └───────────────┬──────────────────────────────────────────────────┘
                       ▼
       ReviewRequest(diff=reduced, instructions=<assembled>, …)
                       │
              engine.review(req) ─► ReviewResult
                       │
       upsert_sticky(pr, result, classification=result_cls, loaded_skills=[…])  (D-13)
```

### Recommended Project Structure
```
src/prevue/
├── skills/
│   ├── __init__.py
│   ├── loader.py            # load_skills(), select_skills(), assemble_instructions()
│   ├── models.py            # Skill pydantic model (name/description/applies_to + bundle/path)
│   ├── security/
│   │   ├── committed-secrets.md      # MANDATORY (D-11)
│   │   ├── authn-authz.md
│   │   └── input-validation.md
│   ├── frontend/
│   │   ├── accessibility.md
│   │   └── component-state.md
│   ├── backend/
│   │   ├── error-handling.md
│   │   └── api-contracts.md
│   ├── data/
│   │   ├── migrations.md
│   │   └── sql-safety.md
│   └── infra/
│       ├── iac-safety.md
│       └── ci-workflow-hardening.md
```
**Packaging note:** `src/prevue/skills/**/*.md` must ship in the wheel. With the `uv_build` backend (current build system), package data under the package dir is included by default for the src layout, but the planner should add a Wave 0 / verification step that confirms `importlib.resources.files("prevue.skills")` can read a `.md` after a build (mirror how `default_rules.yml` is already packaged inside `prevue.classify`). `[ASSUMED]` — verify packaging picks up nested `.md` resources.

### Pattern 1: Packaged-data load (mirror rules.py exactly)
**What:** Resolve the skills tree from the installed package, never the filesystem `__file__`.
**When to use:** Always — this is the SKIL-04 trusted-ref-by-construction mechanism (D-10) and the T-A2 convention from Phase 1.
**Example:**
```python
# Source: existing prevue/classify/rules.py (load_default_rules), generalized to a tree
import importlib.resources

def _skills_root():
    # Returns a Traversable rooted at the packaged framework skills dir.
    return importlib.resources.files("prevue.skills")

def _iter_skill_files():
    root = _skills_root()
    for bundle_dir in root.iterdir():
        if not bundle_dir.is_dir() or bundle_dir.name in {"__pycache__"}:
            continue
        for entry in bundle_dir.iterdir():
            if entry.name.endswith(".md"):
                yield bundle_dir.name, entry  # (bundle, Traversable)
```
> Note: `importlib.resources.files()` returns a `Traversable`. For python-frontmatter, read text first (`entry.read_text(encoding="utf-8")`) and call `frontmatter.loads(text)` rather than `frontmatter.load(path)` — `frontmatter.load` expects a filesystem path/file object, but `Traversable` is not guaranteed to be a real path. `frontmatter.loads(text)` is the robust choice here. `[CITED: python-frontmatter.readthedocs.io — loads(text)]`

### Pattern 2: Per-skill glob selection (reuse GitIgnoreSpec — D-05)
**What:** A skill matches if ANY of the PR's changed-file paths match ANY of the skill's `applies-to` globs.
**When to use:** The core selection step.
**Example:**
```python
# Source: reuse of pathspec engine from prevue/classify/classifier.py
from pathspec import GitIgnoreSpec

def _skill_matches(applies_to: list[str], paths: list[str]) -> bool:
    spec = GitIgnoreSpec.from_lines(applies_to)
    return any(spec.match_file(p) for p in paths)
```
> The classifier uses `spec.check_file(path).include` to also recover *which* glob matched (for audit provenance). Phase 3's D-13 audit surfaces skill **names**, not which glob matched, so the simpler `match_file` boolean suffices. If the planner wants per-skill matched-glob provenance later, `check_file().index` is available (same as classifier).

### Pattern 3: Deterministic ordering (D-08)
**What:** Sort matched skills by bundle's canonical rank, then filename alpha.
**Example:**
```python
# Source: reuse CANONICAL_LABEL_ORDER from prevue/classify/models.py
from prevue.classify.models import CANONICAL_LABEL_ORDER

def _rank(bundle: str) -> int:
    try:
        return CANONICAL_LABEL_ORDER.index(bundle)
    except ValueError:
        return len(CANONICAL_LABEL_ORDER)

matched.sort(key=lambda s: (_rank(s.bundle), s.filename))
```
> This mirrors `router._canonical_index` and `comments._canonical_index` verbatim — same fallback-to-end semantics for unknown bundles. The planner could lift a shared `canonical_index()` helper, but D-05's "reuse at helper level" plus the existing two copies suggests a small shared helper in `classify/models.py` would be cleaner than a third copy.

### Pattern 4: Context assembly (D-07)
**What:** Baseline preamble + one delimited section per skill.
**Example:**
```python
def assemble_instructions(baseline: str, skills: list[Skill]) -> str:
    if not skills:                       # D-06 no-match fallback
        return baseline
    sections = [baseline]
    for s in skills:
        sections.append(f"## Skill: {s.name}\n{s.body.strip()}")
    return "\n\n".join(sections)
```

### Anti-Patterns to Avoid
- **Loading whole bundles instead of per-skill (D-04 violation):** the roadmap floor says "backend PR → backend bundle"; the locked decision is finer — load only the *individual skills whose globs match*. Don't gate on `result_cls.bundles`.
- **Reading skills from the PR head / a consumer dir (SKIL-04 violation):** Phase 3 loads ONLY the packaged framework dir. No consumer-skill path exists yet (Phase 6).
- **Re-implementing glob matching (D-05 violation):** reuse `GitIgnoreSpec`.
- **Silently skipping a malformed skill (D-12 violation):** raise. A broken built-in skill is a framework bug CI must catch.
- **Non-deterministic order (filesystem `iterdir()` order):** always sort (D-08) — snapshot tests depend on it.
- **`frontmatter.load(traversable)`:** prefer `frontmatter.loads(read_text())` because `importlib.resources` Traversables aren't guaranteed real paths.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Frontmatter parsing | Manual `---` split + yaml | `python-frontmatter` (`frontmatter.loads`) | Handles no-frontmatter, empty body, BOM, custom delimiters; SafeLoader by default; keeps Agent-Skills portability (STACK.md "never invent a custom skill format") |
| Glob matching | `fnmatch`/`pathlib.match` | `GitIgnoreSpec` (already in repo) | stdlib `**` semantics are wrong; would silently mis-select skills |
| Packaged-file resolution | `os.path` + `__file__` | `importlib.resources.files()` | `__file__` breaks in zip/installed contexts; T-A2 convention; SKIL-04 by construction |
| Canonical ordering | New ordering constant | `CANONICAL_LABEL_ORDER` | Single source of truth in `classify/models.py` |
| Dedupe | ad-hoc | seen-set append (router pattern) | Mirror WR-02 |

**Key insight:** This phase is almost entirely **composition of existing repo helpers** + one new parser dependency. The risk is not algorithmic difficulty; it's discipline: reuse the four existing seams (`GitIgnoreSpec`, `CANONICAL_LABEL_ORDER`, `importlib.resources`, the dedupe pattern) rather than re-creating them.

## Runtime State Inventory

> Greenfield-additive phase (new package + new files). No rename/refactor. Inventory still checked explicitly:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by grep; no datastore, no persisted state in this stateless workflow | none |
| Live service config | None — no external service holds skill names; skills are static repo files | none |
| OS-registered state | None — no scheduler/daemon | none |
| Secrets/env vars | None new — loader reads no secrets; `COPILOT_MODEL`/`COPILOT_GITHUB_TOKEN` unchanged | none |
| Build artifacts | **New packaged data:** `src/prevue/skills/**/*.md` must be included in the wheel by `uv_build`. After adding files, a fresh build/install is needed for `importlib.resources` to see them | Verify packaging includes nested `.md`; reinstall (`uv sync`) after adding skill files |

## Common Pitfalls

### Pitfall 1: `applies-to` is a hyphenated YAML key but Python identifiers use underscore
**What goes wrong:** Frontmatter key is `applies-to` (matches the project's chosen schema, D-02), but a pydantic field can't be named `applies-to`.
**Why it happens:** YAML/Agent-Skills convention uses hyphens; Python uses underscores.
**How to avoid:** Use a pydantic alias: `applies_to: list[str] = Field(alias="applies-to")` and validate with `Skill.model_validate(meta)` (populate-by-alias is the default for `model_validate` when the alias is present). Add `model_config = ConfigDict(populate_by_name=True)` if you also want to accept `applies_to`. `[CITED: pydantic v2 docs — Field(alias=...)]`
**Warning signs:** `ValidationError: field required (applies_to)` even though the file has `applies-to:` — means the alias isn't wired.

### Pitfall 2: Packaged `.md` not shipped in the wheel
**What goes wrong:** Tests pass locally (src on path) but `importlib.resources.files("prevue.skills")` finds no `.md` after an installed build.
**Why it happens:** Build backend didn't include non-`.py` data under nested dirs.
**How to avoid:** Verify with the same mechanism `default_rules.yml` uses (already proven to ship inside `prevue.classify`). Add a test that asserts ≥1 skill file is readable via `importlib.resources`. If `uv_build` misses them, add explicit package-data config.
**Warning signs:** Empty matched-skill list in an installed environment; loader never raises but loads nothing.

### Pitfall 3: Empty `applies-to` list silently matches nothing (or everything)
**What goes wrong:** `GitIgnoreSpec.from_lines([])` matches no paths; a skill with `applies-to: []` would never load — possibly a silent authoring bug.
**Why it happens:** Empty globs are valid YAML but meaningless.
**How to avoid:** D-12 fail-closed — validate `applies_to` is a non-empty `list[str]` in the `Skill` model (`min_length=1`). Treat empty as malformed → raise.
**Warning signs:** A bundle's skill never appears in any review.

### Pitfall 4: Glob anchoring surprises (gitignore semantics)
**What goes wrong:** `applies-to: ["*.py"]` (no `**/`) under gitignore semantics may not match `src/api/main.py` the way authors expect — `GitIgnoreSpec` treats a pattern without a slash as matching at any depth, but patterns with a leading slash anchor to root.
**Why it happens:** gitignore matching ≠ naive glob.
**How to avoid:** Author skill globs in the **same style as `default_rules.yml`** (`**/*.py`, `terraform/**`, `**/.env*`) — D-02/D-11's drafts below already do this. Add a test per bundle that a representative path matches.
**Warning signs:** A backend skill doesn't fire on a clearly-backend PR.

### Pitfall 5: Reintroducing non-determinism via dict/set iteration
**What goes wrong:** Dedupe via set, then emit in set order → flaky snapshot tests.
**How to avoid:** Dedupe with a seen-set but append to an ordered list (router pattern), then explicitly sort (D-08). Never rely on `iterdir()` or set iteration order for output.

## Code Examples

### Skill model (fail-closed frontmatter validation, D-12)
```python
# prevue/skills/models.py
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field

class Skill(BaseModel):
    """A single built-in review-guidance skill (D-02, D-12 fail-closed)."""
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    applies_to: list[str] = Field(alias="applies-to", min_length=1)

    # populated by the loader, not from frontmatter:
    bundle: str = ""        # directory name (security/frontend/…)
    filename: str = ""      # e.g. "committed-secrets.md"
    body: str = ""          # markdown body (frontmatter content)
```

### Loader (parse + validate + select + order, D-03/D-08/D-09/D-12)
```python
# prevue/skills/loader.py
from __future__ import annotations
import importlib.resources
import frontmatter
from pathspec import GitIgnoreSpec
from prevue.classify.models import CANONICAL_LABEL_ORDER
from prevue.skills.models import Skill

def load_skills() -> list[Skill]:
    """Parse + validate every packaged skill. Fail-closed (D-12)."""
    root = importlib.resources.files("prevue.skills")
    skills: list[Skill] = []
    for bundle_dir in root.iterdir():
        if not bundle_dir.is_dir() or bundle_dir.name == "__pycache__":
            continue
        for entry in sorted(bundle_dir.iterdir(), key=lambda e: e.name):
            if not entry.name.endswith(".md"):
                continue
            post = frontmatter.loads(entry.read_text(encoding="utf-8"))
            skill = Skill.model_validate(post.metadata)  # raises on bad meta
            skill.bundle = bundle_dir.name
            skill.filename = entry.name
            skill.body = post.content
            skills.append(skill)
    return skills

def _rank(bundle: str) -> int:
    try:
        return CANONICAL_LABEL_ORDER.index(bundle)
    except ValueError:
        return len(CANONICAL_LABEL_ORDER)

def select_skills(skills: list[Skill], paths: list[str]) -> list[Skill]:
    """Per-skill glob match (D-03/D-05), dedupe by path (D-09), order (D-08)."""
    seen: set[str] = set()
    matched: list[Skill] = []
    for s in skills:
        key = f"{s.bundle}/{s.filename}"
        if key in seen:
            continue
        spec = GitIgnoreSpec.from_lines(s.applies_to)
        if any(spec.match_file(p) for p in paths):
            seen.add(key)
            matched.append(s)
    matched.sort(key=lambda s: (_rank(s.bundle), s.filename))
    return matched

def assemble_instructions(baseline: str, skills: list[Skill]) -> str:
    """Preamble + delimited skill sections (D-07); baseline alone if empty (D-06)."""
    if not skills:
        return baseline
    return "\n\n".join([baseline] + [f"## Skill: {s.name}\n{s.body.strip()}" for s in skills])
```

### `run_review()` integration (the seam — D-06/D-07/D-13)
```python
# prevue/review.py  — insert after the route() line (currently line 51)
from prevue.skills.loader import assemble_instructions, load_skills, select_skills
# ...
result_cls.bundles = route(list(result_cls.labels.keys()), ruleset.routing_map)
result_cls.dropped_count = len(dropped)

skills = load_skills()                                   # raises on bad frontmatter (D-12)
matched = select_skills(skills, [f.path for f in reduced.files])
instructions = assemble_instructions(BASELINE_INSTRUCTIONS, matched)  # D-06/D-07

req = ReviewRequest(diff=reduced, instructions=instructions,
                    budget_seconds=300, model=os.environ.get("COPILOT_MODEL"))
engine = adapter or CopilotCliAdapter()
result = engine.review(req)

loaded = [f"{s.name} ({s.bundle})" for s in matched]     # D-13 audit list
upsert_sticky(pr, result, classification=result_cls, loaded_skills=loaded)
```

### Audit surfacing in comments.py (D-13)
```python
# prevue/github/comments.py — extend render_body() + upsert_sticky() signature
def render_body(result, *, classification=None, loaded_skills=None) -> str:
    ...
    if loaded_skills:
        metadata += "\nSkills: " + ", ".join(loaded_skills)
    elif classification is not None:
        metadata += "\nSkills: none (baseline only)"   # makes the no-match path auditable (D-06)
    ...
def upsert_sticky(pr, result, *, classification=None, loaded_skills=None) -> None:
    body = render_body(result, classification=classification, loaded_skills=loaded_skills)
    _upsert_marker_comment(pr, body)
```
> `loaded_skills` defaults to `None` so existing call sites and tests stay green; the existing `test_run_review_happy_path_calls_upsert_once` reads `call_args.kwargs.get("classification")` and won't break. New `loaded_skills` assertions get added.

## Skill Content Drafts

> D-11: real-but-lean checklists the planner turns into actual `.md` files. Each draft below is a complete file (frontmatter + body). Globs mirror `default_rules.yml` style. **`[ASSUMED]`** — content is drafted from standard code-review best practice; the planner/user may tune wording. The *structure*, the security secrets requirement, and the globs are the load-bearing parts.

### `security/committed-secrets.md` — MANDATORY (D-11)
```markdown
---
name: Committed Secrets & Credentials
description: Flag any secret, credential, token, private key, or password committed in the diff. Alert only — never redact or modify.
applies-to:
  - "**/*"
---
Scan added or modified lines for committed secrets and ALERT (do not redact):
- API keys, access tokens, bearer tokens, OAuth client secrets
- Private keys (`-----BEGIN ... PRIVATE KEY-----`), `.pem`, `.key`, `.p12`
- Passwords / connection strings with embedded credentials (`://user:pass@host`)
- Cloud credentials (AWS access key IDs `AKIA...`, GCP service-account JSON, Azure keys)
- High-entropy strings assigned to names like `token`, `secret`, `password`, `apikey`
- `.env` files or `.env.*` with real values (not placeholders)

For each: report file + line, name the credential type, and recommend rotation + removal from history. Treat hardcoded secrets as **error** severity. Do not echo the full secret value back in the comment — reference it by location.
```
> `applies-to: "**/*"` is deliberate: secret-scanning must run on **every** PR with reviewable files, so this skill always loads. That makes "secrets check" effectively the floor on any non-empty review — consistent with D-11 making it mandatory. (It does NOT trigger the no-match fallback; this skill always matches, so D-06 only fires if even this is somehow absent — which D-12 would catch.)

### `security/authn-authz.md`
```markdown
---
name: Authentication & Authorization
description: Review changes to auth flows, session handling, and access control for privilege and bypass risks.
applies-to:
  - "**/auth/**"
  - "**/*auth*"
  - "**/middleware/**"
  - "**/*session*"
---
- Verify every new endpoint/handler enforces authentication and the correct authorization check (no missing guard).
- Check for broken access control: object-level authorization (IDOR), role checks done client-side only, or trusting user-supplied IDs.
- Session/token handling: secure + httpOnly cookies, expiry, rotation on privilege change, no tokens in URLs or logs.
- Confirm auth failures fail closed (deny by default), and error messages don't leak whether a user exists.
```

### `security/input-validation.md`
```markdown
---
name: Input Validation & Injection
description: Review untrusted-input handling for injection and validation gaps.
applies-to:
  - "**/*.py"
  - "**/*.go"
  - "**/*.rb"
  - "**/*.java"
  - "**/*.ts"
  - "**/*.js"
---
- Parameterized queries / ORM for all SQL — flag string-concatenated queries (SQLi).
- Validate + bound all external input (size, type, range); reject by allowlist, not denylist.
- Shell/subprocess calls: no untrusted data in the command string; avoid `shell=True` with interpolation.
- Path handling: prevent traversal (`../`); resolve + confine to an allowed root.
- Deserialization of untrusted data uses safe loaders (e.g. `yaml.safe_load`, never `pickle` on untrusted input).
```

### `frontend/accessibility.md`
```markdown
---
name: Accessibility
description: Review UI changes for basic accessibility (a11y) compliance.
applies-to:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.vue"
---
- Interactive elements are real controls (`<button>`/`<a>`) or have correct ARIA role + keyboard handlers.
- Images/icons have meaningful `alt` (or are marked decorative).
- Form inputs have associated `<label>`s; error states are announced, not color-only.
- Focus order is logical; no positive `tabindex`; modals trap + restore focus.
```

### `frontend/component-state.md`
```markdown
---
name: Component State & Rendering
description: Review component state management and render correctness.
applies-to:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.vue"
---
- No derived state duplicated into local state when it can be computed during render.
- Effects have correct dependency arrays; no missing deps causing stale closures, no objects/arrays recreated each render as deps.
- Keys on list items are stable + unique (not array index when items reorder).
- Avoid expensive work in render; memoize only where measured.
```

### `backend/error-handling.md`
```markdown
---
name: Error Handling & Resilience
description: Review error handling, logging, and failure modes in backend code.
applies-to:
  - "**/*.py"
  - "**/*.go"
  - "**/*.rb"
  - "**/*.java"
---
- Errors are handled or propagated deliberately — no bare `except:`/swallowed errors that hide failures.
- External calls (DB, HTTP, queue) have timeouts and handle failure; no unbounded retries without backoff.
- Logs include enough context to debug but never secrets/PII; correct log levels.
- Resources (files, connections, locks) released on all paths (context managers / `defer` / `finally`).
```

### `backend/api-contracts.md`
```markdown
---
name: API Contracts & Compatibility
description: Review API surface changes for backward compatibility and correctness.
applies-to:
  - "**/*.py"
  - "**/*.go"
  - "**/api/**"
  - "**/*controller*"
  - "**/routes/**"
---
- Breaking changes to request/response shape, status codes, or required fields are flagged (versioning or migration path needed).
- Input is validated at the boundary; responses don't over-expose internal fields.
- Pagination/limits on list endpoints; no unbounded result sets.
- Idempotency for retryable mutations where appropriate.
```

### `data/migrations.md`
```markdown
---
name: Database Migrations
description: Review schema migrations for safety and reversibility.
applies-to:
  - "**/migrations/**"
  - "**/*.sql"
  - "**/schema.prisma"
---
- Migration is reversible (or the irreversibility is intentional + noted); a down/rollback exists where the tool supports it.
- No long table locks on large tables (avoid blocking `ALTER`; prefer additive + backfill + switch).
- New non-null columns have defaults or a backfill step; no data loss on column drop/rename without a deprecation window.
- Index changes considered for query impact; created concurrently where supported.
```

### `data/sql-safety.md`
```markdown
---
name: SQL Safety
description: Review raw SQL and queries for injection and performance footguns.
applies-to:
  - "**/*.sql"
  - "**/*repository*"
  - "**/*queries*"
---
- No string-built SQL with untrusted input — parameterize.
- Queries have bounded result sets and use indexes for filter/join columns; flag obvious N+1 patterns.
- Transactions wrap multi-statement invariants; isolation level appropriate.
- Destructive statements (`DELETE`/`UPDATE` without `WHERE`, `TRUNCATE`, `DROP`) are intentional and guarded.
```

### `infra/iac-safety.md`
```markdown
---
name: Infrastructure-as-Code Safety
description: Review Terraform / Dockerfiles / K8s manifests for security and reliability.
applies-to:
  - "**/*.tf"
  - "terraform/**"
  - "**/Dockerfile"
  - "**/k8s/**"
---
- No hardcoded secrets in IaC; use secret stores / variables.
- Least privilege: IAM roles/policies, security-group rules, and RBAC are scoped — flag `0.0.0.0/0` ingress and wildcard permissions.
- Containers: pinned base-image tags (not `latest`), non-root user, minimal capabilities.
- Resources have sane limits/requests; storage isn't public by default.
```

### `infra/ci-workflow-hardening.md`
```markdown
---
name: CI / GitHub Actions Hardening
description: Review CI workflow changes for supply-chain and permission risks.
applies-to:
  - ".github/workflows/**"
  - "**/*.yml"
  - "**/*.yaml"
---
- Actions are pinned to a full commit SHA, not a mutable tag.
- `permissions:` is least-privilege (default read; write only where needed); no blanket `write-all`.
- No `pull_request_target` with checkout of PR head + secrets; untrusted input not interpolated into `run:` shells.
- Secrets passed explicitly, never `secrets: inherit` to reusable workflows; no secrets echoed to logs.
```

> Note on glob breadth: `input-validation.md`, `api-contracts.md`, and `ci-workflow-hardening.md` use broad globs (`**/*.py`, `**/*.yml`) that overlap other skills' triggers. That's intentional and correct under D-04 (per-skill independent selection). The planner should ensure the **5-bundle backend-only-PR success criterion** holds: a backend-only `.py` PR loads backend + security(input-validation) + the always-on committed-secrets skill, and NOT frontend/data/infra skills — which is the desired "load only what's needed" behavior. If the user wants stricter isolation, narrow the cross-cutting globs; flagged as an Open Question.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom per-tool skill formats | Agent Skills open spec (SKILL.md frontmatter) | 2025–2026 | Use the open `name`/`description` + metadata-map shape; keeps portability. `applies-to` is a Prevue-specific metadata field (see Open Questions on schema-purity). |
| `pkg_resources` for package data | `importlib.resources.files()` | Python 3.9+ | Already the repo's pattern (`rules.py`); use `Traversable` API. |
| pydantic v1 validators | pydantic v2 (`model_validate`, `Field(alias=...)`, `ConfigDict`) | pydantic 2.x | Repo is on 2.13.4; never mix v1-style. |

**Deprecated/outdated:**
- pathspec `"gitwildmatch"` factory name → `GitIgnoreSpec` / `"gitignore"` in 1.x. Repo already uses `GitIgnoreSpec`. Don't copy 0.12-era snippets.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `uv_build` includes nested `src/prevue/skills/**/*.md` in the wheel without extra config | Project Structure / Pitfall 2 | If wrong, installed loader finds no skills; needs explicit package-data config. **Mitigate: add a packaged-resource read test (Wave 0).** Note `default_rules.yml` already ships inside `prevue.classify`, so precedent is strong. |
| A2 | The drafted skill bodies + globs are acceptable content | Skill Content Drafts | Low — D-11 explicitly delegates content to researcher draft + user tuning; only the security-secrets requirement and glob-style are load-bearing. |
| A3 | `committed-secrets.md` should use `applies-to: "**/*"` (always-on) | Skill Content Drafts | If the user wants secrets-scan only on certain paths, narrow it — but D-11 calls it mandatory, so always-on is the safe reading. |
| A4 | python-frontmatter is safe to install (SUS verdict is a false positive) | Package Legitimacy Audit | Low — STACK.md HIGH-confidence recommendation + real PyPI repo URL confirmed; planner still gates with checkpoint:human-verify per protocol. |
| A5 | Surfacing "Skills: none (baseline only)" when no skill matches is desired audit behavior | comments.py example / D-13 | Low — makes the D-06 path auditable; user may prefer omitting the line. |

## Open Questions

1. **`applies-to` schema purity vs Agent Skills spec.**
   - What we know: agentskills.io requires `name` + `description`; extra keys go in an optional `metadata:` map. The project chose top-level `applies-to` (D-02).
   - What's unclear: whether top-level `applies-to` (vs `metadata: {applies-to: [...]}`) compromises the "never invent a custom format / stay portable" commitment in STACK.md.
   - Recommendation: D-02 is locked at top-level `applies-to`; honor it. To preserve portability, the `Skill` model can `model_config = ConfigDict(extra="ignore")` so real Agent-Skills files with a `metadata` map still parse. If strict spec-compliance matters later, move `applies-to` under `metadata` — a small, mechanical change. **Tag the chosen location as a decision for the planner to confirm.**

2. **Cross-cutting glob breadth (e.g. `input-validation.md: **/*.py`).**
   - What we know: broad globs make a security skill load on most backend PRs — arguably desirable (security-first), but it widens context.
   - What's unclear: whether the user wants strict per-domain isolation or security-skills-as-floor.
   - Recommendation: keep broad for security (defends the secrets/validation thesis); the backend-only success criterion still passes because frontend/data/infra skills don't match `.py`. Confirm with user if token tightness is a priority.

3. **Shared `canonical_index()` helper.**
   - What we know: `router.py`, `comments.py`, and now the loader each need bundle→rank. Two copies exist; Phase 3 adds a third.
   - Recommendation: lift a single `canonical_index(name)` into `classify/models.py` (next to `CANONICAL_LABEL_ORDER`) and have all three import it (DRY, aligns with D-05's helper-level reuse). Low-risk refactor; planner's call.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python-frontmatter | Skill frontmatter parsing | ✗ (not yet installed) | target 1.3.* | none — must `uv add` |
| pathspec | Per-skill glob match | ✓ | 1.1.1 | — |
| pydantic | Skill model validation | ✓ | 2.13.4 | — |
| PyYAML | frontmatter YAML backend | ✓ | 6.0.* | — |
| uv | Dependency install | ✓ (project uses it) | — | — |

**Missing dependencies with no fallback:**
- `python-frontmatter` — must be added (`uv add python-frontmatter==1.3.*`) before the loader can import it. Gate behind `checkpoint:human-verify` per the legitimacy audit.

**Missing dependencies with fallback:** none.

## Validation Architecture

> nyquist_validation not disabled in config (`.planning/config.json` absent / not set false) → section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (+ pytest-cov 7.1.0) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| Quick run command | `uv run pytest tests/test_skills_loader.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SKIL-01 | backend-only PR loads backend + security skills, NOT frontend/data/infra | unit | `uv run pytest tests/test_skills_loader.py::test_backend_only_pr_selects_backend_not_frontend -x` | ❌ Wave 0 |
| SKIL-01 | dedupe by path (D-09) — skill with two matching globs loads once | unit | `uv run pytest tests/test_skills_loader.py::test_dedupe_by_path -x` | ❌ Wave 0 |
| SKIL-01 | deterministic order (D-08) — canonical bundle then filename | unit | `uv run pytest tests/test_skills_loader.py::test_canonical_then_filename_order -x` | ❌ Wave 0 |
| SKIL-01 | no-match → BASELINE_INSTRUCTIONS alone (D-06) | unit | `uv run pytest tests/test_skills_loader.py::test_no_match_falls_back_to_baseline -x` | ❌ Wave 0 |
| SKIL-01 | assembled instructions = preamble + `## Skill:` sections (D-07) | unit/snapshot | `uv run pytest tests/test_skills_loader.py::test_assemble_sections -x` | ❌ Wave 0 |
| SKIL-02 | all 5 bundle dirs exist; every built-in skill parses + validates | unit | `uv run pytest tests/test_skills_builtin.py::test_all_builtin_skills_valid -x` | ❌ Wave 0 |
| SKIL-02 | security bundle includes committed-secrets skill | unit | `uv run pytest tests/test_skills_builtin.py::test_security_secrets_skill_present -x` | ❌ Wave 0 |
| SKIL-02/D-12 | malformed frontmatter (missing applies-to / empty list) raises | unit | `uv run pytest tests/test_skills_loader.py::test_missing_applies_to_raises -x` | ❌ Wave 0 |
| SKIL-04 | load path is the packaged framework dir (importlib.resources), not `__file__`/PR head | unit | `uv run pytest tests/test_skills_loader.py::test_loads_from_packaged_framework_dir -x` | ❌ Wave 0 |
| SKIL-04 | packaged `.md` readable via importlib.resources (packaging guard) | unit | `uv run pytest tests/test_skills_builtin.py::test_skills_packaged_and_readable -x` | ❌ Wave 0 |
| D-13 | run_review threads loaded skill names+bundles into upsert_sticky | unit | `uv run pytest tests/test_review_flow.py::test_loaded_skills_in_metadata -x` | ⚠️ extend existing file |
| D-13 | render_body emits `Skills:` line | unit | `uv run pytest tests/test_comments.py::test_render_body_loaded_skills -x` | ⚠️ extend existing file |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_skills_loader.py tests/test_skills_builtin.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green + `uv run ruff check` before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_skills_loader.py` — covers SKIL-01, D-06/08/09, D-12, SKIL-04 selection/order/fail-closed
- [ ] `tests/test_skills_builtin.py` — covers SKIL-02 (5 bundles, secrets skill, all-valid, packaged-readable)
- [ ] Extend `tests/test_review_flow.py` — D-13 loaded-skills threading (the existing happy-path test reads `instructions == BASELINE_INSTRUCTIONS`; **that assertion will change** once a matching skill loads — update it)
- [ ] Extend `tests/test_comments.py` — D-13 `Skills:` metadata line
- [ ] Dependency install: `uv add python-frontmatter==1.3.*` (behind checkpoint:human-verify)
- [ ] Conftest fixture: a tmp skills tree (or a `tests/fixtures/skills/` dir) for loader-unit tests that don't depend on the real built-in content

> **Heads-up for the planner:** `tests/test_review_flow.py::test_run_review_happy_path_calls_upsert_once` currently asserts `req.instructions == BASELINE_INSTRUCTIONS` on a `src/example.py` PR. After Phase 3, a backend `.py` PR will match backend/security skills, so `instructions` will NO LONGER equal the bare baseline. This test MUST be updated as part of the phase (it's a behavior change, not a regression).

## Security Domain

> `security_enforcement` not disabled → included. This phase has a direct security mandate (D-11 secrets-flagging) and a trust-boundary requirement (SKIL-04).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture / Trust Boundaries | yes | SKIL-04: skills load only from the packaged framework dir (`importlib.resources.files("prevue.skills")`), never from PR-modifiable files. Invariant asserted + tested (D-10). |
| V5 Input Validation | yes | Skill frontmatter validated fail-closed via pydantic `Skill` model (D-12); python-frontmatter uses `yaml.SafeLoader` (no arbitrary object construction). |
| V6 Cryptography / Secrets | yes (as review subject) | The `committed-secrets.md` skill instructs the engine to flag secrets in the diff — alert, not redact (D-11). This is a *review capability* Prevue ships, not crypto Prevue performs. |
| V14 Configuration / Supply Chain | yes | New dep `python-frontmatter` gated via package-legitimacy audit + checkpoint:human-verify (SUS verdict, likely false positive). |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Untrusted PR modifies a skill file to weaken/poison the review prompt | Tampering | SKIL-04: load only from the trusted packaged framework dir; never the PR head (D-10). Asserted invariant + test. |
| Malicious/malformed frontmatter crashes or silently disables a skill | DoS / Tampering | D-12 fail-closed: validate on load, raise. A broken built-in is a CI-caught framework bug, not a runtime PR condition. |
| Unsafe YAML deserialization in frontmatter | Tampering / RCE | python-frontmatter uses `yaml.SafeLoader` by default (`[CITED: eyeseast/python-frontmatter default_handlers.py]`); never switch to full `yaml.load`. Built-in skills are trusted anyway, but SafeLoader is correct defense-in-depth. |
| Supply-chain risk in the new parser dependency | Tampering | Legitimacy audit + checkpoint:human-verify before `uv add`; pin `python-frontmatter==1.3.*`; commit `uv.lock`. |
| Skill body echoes a found secret back in the PR comment | Information Disclosure | The `committed-secrets.md` body instructs: reference secrets by location, do not echo the full value (alert-not-redact, but also don't republish). |

## Sources

### Primary (HIGH confidence)
- **Repo source code** (`classify/rules.py`, `classify/classifier.py`, `classify/filter.py`, `classify/router.py`, `classify/models.py`, `review.py`, `models.py`, `github/comments.py`, `classify/default_rules.yml`, `tests/*`) — exact seams, signatures, conventions, reuse points. Read this session.
- **Executed in repo venv:** `pathspec.__version__ == 1.1.1`, `pydantic.VERSION == 2.13.4`. `[VERIFIED]`
- **PyPI** `https://pypi.org/pypi/python-frontmatter/json` — name/version 1.3.0 / requires_python>=3.10 / uploaded 2026-05-20 / repository URL. `[VERIFIED]`
- `.planning/research/STACK.md` — python-frontmatter 1.3.0, pathspec 1.1.1, Agent Skills spec, "never invent a custom format". `[CITED]`

### Secondary (MEDIUM confidence)
- `https://python-frontmatter.readthedocs.io` — `load`/`loads`, `.metadata`/`.content`, `frontmatter.dumps`. `[CITED]`
- `https://github.com/eyeseast/python-frontmatter` `default_handlers.py` — `SafeLoader` default. `[CITED]`

### Tertiary (LOW confidence)
- Skill-content drafts — standard code-review best practice, not from a single authoritative source. `[ASSUMED]` (D-11 explicitly delegates content to draft + user tuning).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all deps already in repo except python-frontmatter, which is PyPI-verified + SafeLoader-confirmed at source.
- Architecture/seams: HIGH — read every relevant file; integration point is a single, well-defined insertion in `run_review()`.
- Skill content: LOW (by design) — drafted; D-11 delegates specifics to user tuning.
- Packaging (nested `.md` in wheel): MEDIUM — strong precedent (`default_rules.yml` ships in `prevue.classify`) but needs a confirming test (A1).

**Research date:** 2026-06-12
**Valid until:** 2026-07-12 (stable stack; python-frontmatter/pathspec/pydantic are mature)
