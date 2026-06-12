# Phase 2: Zero-Token Classification & Routing - Research

**Researched:** 2026-06-11
**Domain:** Deterministic file classification (gitignore-style glob matching) + label→bundle routing, pure-function pipeline inside an existing pydantic/PyGithub codebase
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 — Multi-label union.** A PR spanning domains (`.tsx` + Terraform) receives *every* matched label; downstream loads the union of matched bundles. No single-dominant-label tie-break.
- **D-02 — `general` fallback label.** Files matching no deterministic rule fall back to a `general` label routing to a baseline/general bundle. Deterministic, zero-token, never leaves a file un-reviewed. Phase 5's LLM fallback later upgrades `general` → specific.
- **D-03 — `general` fires only when NO file in the PR matched a real rule.** If any file got a real label, route to those bundles only and fold unmatched file(s) into that review. A `.tsx` + one odd file stays frontend-only.
- **D-04 — Built-in default rules ship as a repo data file (YAML).** Glob→label rules are data, not code (CLSF-03).
- **D-05 — Consumer rules in `.github/prevue.yml` are additive / override-by-label** (extend or override the built-in set; not a full replace).
- **D-06 — label→bundle routing map defaults 1:1 by name, overridable.** Routing precedence (consumer override > consumer custom > built-in) is the Phase 3 contract; Phase 2 only needs the overridable map.
- **D-07 — Default noise filters (lockfiles, generated, vendored, binary) and consumer ignore globs are additive** — consumer globs add to the built-ins (not replace).
- **D-08 — Filtered files are dropped from BOTH classification and the review diff the engine sees.** Modifies the `DiffBundle` before it reaches the engine — interacts with `run_review()`.
- **D-09 — Surface assigned labels + the matched rule per label in the sticky comment's Metadata section** (the D-04 placeholder from Phase 1). Compact — labels + matched rule, not a full per-file dump.
- **D-10 — Empty-PR neutral skip.** A PR where ALL files are filtered out (e.g. lockfile-only) → no engine call, post a sticky note "no reviewable files (N filtered)". Zero tokens. Not an error, not a `general` review.

### Claude's Discretion

- Classifier module layout, rule-data file path/schema, and the glob-matching implementation. STACK.md recommends **pathspec 1.1.1** (`GitIgnoreSpec`) and **PyYAML 6.0.3** — planner should honor these unless a better fit emerges. pathspec 1.x renamed the pattern factory ("gitwildmatch" → "gitignore"); don't copy 0.12-era snippets.
- How labels/rules attach to the existing pydantic models (extend `DiffBundle`/`ChangedFile` vs a new classification result model).
- Default rule set contents (which globs → which of the 5 labels).

### Deferred Ideas (OUT OF SCOPE)

- **LLM fallback classification** (→ Phase 5, CLSF-02): Phase 2 only provides the deterministic `general` seam. No AI/LLM integration in this phase.
- **Skill bundle loading + the 5 built-in SKILL.md bundles** (→ Phase 3, SKIL-01/02/04): Phase 2 emits bundle **identifiers** only. Do NOT research skill loading mechanics.
- **Inline comments / merge gate** (→ Phase 4): routing/labels feed severity + gating later; not here.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DIFF-02 | Apply default path filters (lockfiles, generated, vendored, binaries) + consumer ignore globs before classification | "Path Filtering" pattern + default noise-glob set (Code Examples §Filter); `GitIgnoreSpec.match_file` for git-exact filtering; D-08 drops from `DiffBundle.files`; D-10 empty-PR skip |
| CLSF-01 | Deterministic classifier assigns category labels (security, frontend, backend, data, infra) from globs/paths/extensions at zero token cost | "Per-label spec" classification pattern; pure function `classify(files, ruleset) → labels`; default rule set table; zero subprocess/network call = zero tokens by construction |
| CLSF-03 | Classification rules are data (configurable/overridable); resulting labels + matched rules auditable in output | YAML rule-data file (D-04); pydantic `RuleSet` model; `GitIgnoreSpec.check_file().index` → matched-rule provenance for the audit trail (D-09) |
| ROUT-01 | Router maps labels → skill bundles with precedence: consumer override > consumer custom > built-in | label→bundle map (D-06); 1:1-by-name default; precedence resolution pattern; emits bundle **identifiers** only (Phase 3 loads them) |
</phase_requirements>

## Summary

Phase 2 inserts a pure, zero-token classification stage between Phase 1's `fetch_diff()` and `engine.review()`. The work decomposes into four pure functions over the existing `DiffBundle`: (1) **filter** noise/ignored files out of `DiffBundle.files`, (2) **classify** the surviving files into the 5 category labels via data-driven globs, (3) **route** labels → skill-bundle identifiers with documented precedence, and (4) **render** the labels + matched-rules audit trail into the sticky comment's Metadata section. Two edge behaviors are first-class: the `general` fallback (D-02/D-03) and the empty-PR neutral skip (D-10).

The single most important technical finding: **pathspec 1.1.1 `GitIgnoreSpec.check_file(path)` returns a `CheckResult(file, include, index)` where `index` is the position of the matching pattern in the `from_lines(...)` list.** This `index` is exactly the "which rule matched" signal D-09 needs — you get audit provenance for free from the matcher, with no separate bookkeeping. Gitignore semantics also apply (last-match-wins, `!negation`, directory-prefix matching, leading-`/` anchoring), which is what makes consumer-additive rules (D-05/D-07) behave intuitively.

The classification and routing logic are pure functions with fully defined I/O (files + ruleset in → labels out; labels + map in → bundle-ids out), which is ideal for the TDD mode this phase runs under. No external services, no network, no subprocess — "zero token" is guaranteed by construction, not by measurement.

**Primary recommendation:** Add `pathspec==1.1.*` and `PyYAML==6.0.*` to `pyproject.toml`. Build four pure functions in a new `src/prevue/classify/` package, ship default rules as a YAML data file inside the package, model the ruleset/result with pydantic, and use **one `GitIgnoreSpec` per label** (plus one for filters) so `check_file().index` yields the matched-rule string for the audit trail. Insert the stage in `run_review()`; render the trail in `comments.render_body()`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Noise/ignore path filtering (DIFF-02) | Pure logic (`classify/filter.py`) | Orchestration (`review.py` applies result to `DiffBundle`) | Glob matching is a pure function of `ChangedFile.path`; mutation of the bundle happens at the orchestration seam |
| Deterministic label classification (CLSF-01) | Pure logic (`classify/classifier.py`) | — | Pure `(files, ruleset) → labels`; no I/O, deterministic, zero-token by construction |
| Rule-data loading (CLSF-03) | Config/Storage (`classify/rules.py`) | Pure logic (validates into pydantic `RuleSet`) | Built-in YAML in the package + consumer `.github/prevue.yml` from trusted base ref; parse + merge is data-tier |
| Label→bundle routing (ROUT-01) | Pure logic (`classify/router.py`) | — | Pure `(labels, routing_map) → bundle_ids`; precedence resolution is deterministic |
| Audit-trail rendering (D-09) | Presentation (`github/comments.py`) | — | Labels + matched rules formatted into the existing Metadata section |
| Empty-PR neutral skip (D-10) | Orchestration (`review.py`) | Presentation (sticky note) | Branch decision belongs at the orchestration seam where the engine call is gated |

**Key correctness note:** classification/routing/filtering are *pure* and belong in `src/prevue/classify/`. The only places that touch I/O or mutate state are `review.py` (orchestration + the D-10 skip branch) and `comments.py` (rendering). Do not let glob-matching logic leak into the GitHub I/O modules.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pathspec | 1.1.1 | Gitignore-style `**` glob matching for both filtering and classification | The de-facto Python gitignore matcher; a dependency of Black, pip, setuptools. `GitIgnoreSpec.check_file()` gives git-exact semantics **and** matched-pattern index for the audit trail. `[VERIFIED: PyPI — latest 1.1.1, published 2026-04-27, requires_python >=3.9]` |
| PyYAML | 6.0.3 | Parse the built-in rules YAML + consumer `.github/prevue.yml` | The standard YAML parser; already a transitive dep of python-frontmatter (Phase 3). Don't add a second YAML lib. `[VERIFIED: PyPI — latest 6.0.3, requires_python >=3.8]` |
| pydantic | 2.13.* | Typed models for `RuleSet`, routing map, classification result | Already locked in the project (Phase 1). Validate the data-driven config at the system boundary. `[VERIFIED: pyproject.toml already pins pydantic==2.13.*]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (stdlib) `importlib.resources` | n/a | Load the built-in rules YAML packaged inside `src/prevue/` | Use `importlib.resources.files("prevue.classify") / "default_rules.yml"` so the data file is found whether installed or run from source. Never hard-code a filesystem path. `[CITED: docs.python.org importlib.resources]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pathspec `GitIgnoreSpec` | stdlib `fnmatch` / `pathlib.PurePath.match` | **Never.** stdlib does not implement `**` gitignore semantics correctly; edge cases (e.g. `**/*.tsx` at depth, directory-prefix matching) silently misclassify. STACK.md "What NOT to Use" confirms. |
| pathspec `GitIgnoreSpec` | pathspec `PathSpec.from_lines("gitwildmatch", ...)` | `PathSpec` works but `GitIgnoreSpec` is the 1.x ergonomic wrapper that defaults to gitignore semantics incl. last-match-wins for negation. Use `GitIgnoreSpec`. |
| One spec mapping index→label | One big `GitIgnoreSpec` for all labels | A single combined spec only tells you *that* a line matched, and with last-match-wins a `.tsx` could be shadowed by a later rule. **Use one `GitIgnoreSpec` per label** (see Pattern 2) so multi-label union (D-01) and per-label matched-rule provenance both work. |

**Installation:**
```bash
# Add to pyproject.toml [project].dependencies, then:
uv add "pathspec==1.1.*" "PyYAML==6.0.*"
uv sync
```
Current `pyproject.toml` pins only `pydantic==2.13.*` and `pygithub==2.9.*` — pathspec and PyYAML are **not yet declared** and must be added in this phase. `[VERIFIED: read pyproject.toml]`

**Version verification (run 2026-06-11):**
- `pathspec` → latest **1.1.1**, published 2026-04-27, `requires_python >=3.9` (project floor is 3.12 ✓). `[VERIFIED: PyPI JSON API]`
- `PyYAML` → latest **6.0.3**, `requires_python >=3.8` (project floor is 3.12 ✓). `[VERIFIED: PyPI JSON API]`

## Package Legitimacy Audit

> Both packages are already documented in the project's verified STACK.md and CLAUDE.md. The legitimacy seam returned `SUS` for both, but the reasons are **metadata artifacts, not genuine risk** (see note below).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| pathspec | PyPI | 1.1.1 published 2026-04-27; project Production/Stable, years of history | unknown via API (huge in reality — dep of Black/pip/setuptools) | github.com/cpburnz/python-pathspec | OK (seam said SUS) | Approved |
| PyYAML | PyPI | 6.0.3, 6.x line stable since 2021 | unknown via API (top-20 most-downloaded PyPI pkg) | pyyaml.org → github.com/yaml/pyyaml | OK (seam said SUS) | Approved |

**Why the seam's `SUS` is a false positive here:**
- The PyPI JSON API does **not** expose weekly download counts, so the seam recorded `unknown-downloads` for *every* PyPI package — not a signal specific to these two.
- pathspec's PyPI metadata omits a machine-readable `repoUrl` field (`no-repository`), but the real repo is `github.com/cpburnz/python-pathspec` (verified via the PyPI project page), maintained by Caleb P. Burns, classified Production/Stable, supporting Python 3.9–3.14. It is a dependency of Black, pip, and setuptools.
- Neither package declares a `postinstall`/install script; neither is deprecated.
- Both are in the project's pre-existing verified STACK.md (versions fetched live 2026-06-12).

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** pathspec, PyYAML — **overridden to OK** based on the source-provenance verification above. No `checkpoint:human-verify` task required; these are foundational ecosystem packages already vetted in STACK.md. The planner may, at its discretion, add a one-line note that the SUS was a metadata artifact.

## Architecture Patterns

### System Architecture Diagram

```
GitHub PR event
      │
      ▼
fetch_diff()  ──►  DiffBundle { files: [ChangedFile{path,status,patch,...}] }   (Phase 1, unchanged)
      │
      ▼
┌─────────────────────── NEW: classification stage (pure) ───────────────────────┐
│                                                                                 │
│  load_rules()                                                                   │
│    built-in default_rules.yml  ──┐                                              │
│    consumer .github/prevue.yml ──┤── merge (additive/override-by-label) ──► RuleSet
│      (trusted base ref only)     ┘                                              │
│                                                                                 │
│  filter(DiffBundle, RuleSet.ignore_globs)                                       │
│     drop lockfiles/generated/vendored/binary + consumer ignores                 │
│        │                                                                        │
│        ├──► all files dropped? ──► (D-10) neutral skip ──► sticky "no reviewable │
│        │                                                    files (N filtered)"  │
│        │                                                    NO engine call ──► END
│        ▼                                                                        │
│     reduced DiffBundle.files                                                    │
│        │                                                                        │
│  classify(files, RuleSet.label_rules)                                           │
│     per-label GitIgnoreSpec.check_file(path) → {label: matched_rule}            │
│        │                                                                        │
│        ├──► no file matched ANY real rule? ──► (D-02/D-03) labels = {"general"} │
│        ▼                                                                        │
│     labels (union, D-01) + matched-rule provenance                             │
│        │                                                                        │
│  route(labels, RuleSet.routing_map)                                            │
│     precedence: consumer override > consumer custom > built-in (1:1 default)    │
│        ▼                                                                        │
│     bundle_ids (identifiers only — Phase 3 loads them)                          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
      │
      ▼
ReviewRequest(diff=reduced DiffBundle, ...)  + classification result threaded alongside
      │
      ▼
engine.review(req)        (Phase 1, unchanged — sees only the filtered diff, D-08)
      │
      ▼
upsert_sticky(pr, result, classification)  ──► Metadata section renders labels + matched rules (D-09)
```

### Recommended Project Structure
```
src/prevue/
├── classify/                  # NEW — pure classification logic
│   ├── __init__.py
│   ├── models.py              # pydantic: Rule, RuleSet, ClassificationResult
│   ├── rules.py               # load + merge built-in YAML with consumer prevue.yml
│   ├── default_rules.yml      # built-in glob→label rules + default ignore globs (D-04)
│   ├── filter.py              # filter(files, ignore_globs) -> kept, dropped
│   ├── classifier.py          # classify(files, label_rules) -> ClassificationResult
│   └── router.py              # route(labels, routing_map) -> list[bundle_id]
├── models.py                  # extend or add ClassificationResult (Claude's discretion)
├── review.py                  # MODIFIED — insert stage, D-10 skip branch
└── github/
    └── comments.py            # MODIFIED — render audit trail in Metadata (D-09)
```

### Pattern 1: Path Filtering (DIFF-02, D-07, D-08)
**What:** Build one `GitIgnoreSpec` from the merged ignore-glob list (built-in noise globs + consumer ignores, additive). Partition `DiffBundle.files` into kept vs dropped. Produce a *new* `DiffBundle` with only kept files so the engine never sees noise (D-08).
**When to use:** Always, before classification.
**Example:**
```python
# Source: pathspec 1.1.1 API verified locally 2026-06-11
from pathspec import GitIgnoreSpec
from prevue.models import ChangedFile, DiffBundle

def filter_diff(diff: DiffBundle, ignore_globs: list[str]) -> tuple[DiffBundle, list[ChangedFile]]:
    spec = GitIgnoreSpec.from_lines(ignore_globs)
    kept, dropped = [], []
    for f in diff.files:
        (dropped if spec.match_file(f.path) else kept).append(f)
    reduced = diff.model_copy(update={"files": kept})
    return reduced, dropped
```

### Pattern 2: Per-Label Classification with Matched-Rule Provenance (CLSF-01, CLSF-03, D-01, D-09)
**What:** Hold **one `GitIgnoreSpec` per label**. For each file, ask each label's spec `check_file(path)`; on a positive `include`, record the label and the matched pattern string (via the returned `index` into that label's pattern list). Union across all files gives the multi-label set (D-01); the recorded pattern strings feed the audit trail (D-09).
**When to use:** Core classification step.
**Why per-label, not one combined spec:** A single combined spec with last-match-wins would let a later rule shadow an earlier `.tsx` match, and you'd lose the label→pattern mapping. One spec per label keeps each label's match independent and gives clean provenance.
**Example:**
```python
# Source: pathspec 1.1.1 CheckResult API verified locally 2026-06-11
from pathspec import GitIgnoreSpec

def classify(files, label_rules: dict[str, list[str]]):
    # label_rules: {"frontend": ["**/*.tsx", "**/*.jsx"], "infra": ["terraform/**", ...], ...}
    specs = {label: GitIgnoreSpec.from_lines(globs) for label, globs in label_rules.items()}
    labels: dict[str, str] = {}          # label -> first matched glob (for audit)
    for f in files:
        for label, spec in specs.items():
            res = spec.check_file(f.path)         # CheckResult(file, include, index)
            if res.include and label not in labels:
                labels[label] = label_rules[label][res.index]   # the matched glob string
    if not labels:                                # D-02/D-03: nothing matched a real rule
        labels = {"general": "(no rule matched)"}
    return labels                                  # e.g. {"frontend": "**/*.tsx"}
```
> **Verified behavior:** `GitIgnoreSpec.from_lines(["**/*.tsx","terraform/**"]).check_file("src/App.tsx")` → `CheckResult(file='src/App.tsx', include=True, index=0)`; a non-match → `CheckResult(..., include=None, index=None)`. `index` maps back to the `from_lines` list position. `[VERIFIED: local execution of pathspec 1.1.1]`

### Pattern 3: Rule Loading & Additive Merge (CLSF-03, D-04, D-05, D-07)
**What:** Load built-in `default_rules.yml` from the package; load consumer `.github/prevue.yml` **from the trusted base ref only** (never from PR-modified files — WKFL-03/SECR-01 posture); merge additively/override-by-label. Validate into a pydantic `RuleSet`.
**When to use:** Once per run, before filter/classify.
**Example:**
```python
# Source: importlib.resources — docs.python.org; PyYAML safe_load
import yaml
from importlib.resources import files

def load_default_rules() -> dict:
    text = (files("prevue.classify") / "default_rules.yml").read_text(encoding="utf-8")
    return yaml.safe_load(text)          # NEVER yaml.load without SafeLoader

def merge_rules(builtin: dict, consumer: dict | None) -> dict:
    # additive/override-by-label (D-05): consumer label globs extend or replace per label;
    # consumer ignore globs append to built-in ignores (D-07).
    ...
```
> **Security:** Always `yaml.safe_load`, never `yaml.load(...)` without a safe loader — arbitrary YAML can instantiate Python objects. The consumer config is read from the *trusted base ref*, but defense-in-depth still applies. `[CITED: PyYAML docs — yaml.safe_load]`

### Pattern 4: Routing with Precedence (ROUT-01, D-06)
**What:** `route(labels, routing_map)` maps each label to a bundle identifier. Default map is 1:1 by name (`frontend → frontend`); consumer overrides win. Phase 2 emits identifier **strings**, not loaded bundles.
**When to use:** After classification, before threading the result to the request/sticky.
**Precedence (D-06):** consumer override > consumer custom > built-in. In Phase 2 this resolves to: if the consumer routing map has an entry for a label, use it; else use the built-in default (1:1 by name).

### Anti-Patterns to Avoid
- **`fnmatch`/`pathlib.match` for `**`:** silently wrong; misclassifies at depth. Use `GitIgnoreSpec`.
- **One combined `GitIgnoreSpec` for all labels:** loses per-label provenance and lets last-match-wins shadow earlier matches. One spec per label.
- **Copying pathspec 0.12-era snippets** (`PathSpec.from_lines("gitwildmatch", ...)`): the factory was renamed in 1.x. Use `GitIgnoreSpec.from_lines(...)`.
- **`yaml.load()` without SafeLoader:** code-execution surface. Use `yaml.safe_load`.
- **Reading consumer `prevue.yml` from the PR head/checkout:** that's untrusted PR content. Read from the trusted base ref only.
- **Mutating the original `DiffBundle` in place:** use `model_copy(update={"files": kept})` so the filter step is a pure transform and tests stay clean.
- **Tagging nearly every PR `general`:** D-03 guards this — `general` only when *no* file matched any real rule.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| `**`/gitignore glob semantics | Custom regex or `fnmatch` loop | `pathspec.GitIgnoreSpec` | Directory-prefix matching, last-match-wins negation, leading-`/` anchoring, depth-independent `*.ext` — all subtle, all already correct in pathspec |
| "Which rule matched this file?" | Re-matching each pattern to find the hit | `GitIgnoreSpec.check_file().index` | The matcher already computes and returns the matching pattern index — free audit provenance |
| YAML parsing | Manual config parser | `yaml.safe_load` | Edge cases (anchors, multiline, types); safe_load also closes a code-exec hole |
| Locating the packaged rules file | `os.path.join(__file__, ...)` | `importlib.resources.files(...)` | Works whether installed as a wheel or run from source; `__file__`-relative paths break under zip/editable installs |

**Key insight:** The entire "auditable, data-driven, deterministic" requirement set (CLSF-03 + D-09) is satisfied almost entirely by leaning on `GitIgnoreSpec.check_file()` returning the matched pattern index. Hand-rolling glob matching would force you to also hand-roll provenance — double the surface area for misclassification bugs.

## Common Pitfalls

### Pitfall 1: pathspec 0.12 → 1.x factory rename
**What goes wrong:** Code copied from old tutorials uses `PathSpec.from_lines("gitwildmatch", lines)`; the "gitwildmatch" string factory was renamed to "gitignore" in 1.x, and the ergonomic path is `GitIgnoreSpec.from_lines(lines)`.
**Why it happens:** Most search results predate pathspec 1.x.
**How to avoid:** Use `from pathspec import GitIgnoreSpec` and `GitIgnoreSpec.from_lines([...])`. Verified working on 1.1.1.
**Warning signs:** `ValueError`/`KeyError` about an unknown pattern factory, or import errors.

### Pitfall 2: Gitignore directory-prefix semantics over-match
**What goes wrong:** A rule like `src/api` (bare, no trailing glob) matches *everything under* `src/api/` (gitignore directory semantics) — verified: `src/api` → `src/api/foo.py` is True. Authors expecting exact-file matching get surprised.
**Why it happens:** gitignore treats a bare path as a directory prefix.
**How to avoid:** Be explicit in `default_rules.yml`: use `src/api/**` for "everything under", `**/*.py` for extensions, leading `/` to anchor to repo root (`/Dockerfile` matches root only, not `sub/Dockerfile` — verified). Document the convention next to the rules.
**Warning signs:** A rule catching more files than intended in tests.

### Pitfall 3: Multi-label union vs `general` interaction (D-01 vs D-03)
**What goes wrong:** Treating `general` as just another label in the union, so a `.tsx` + one unmatched file yields `{frontend, general}` instead of `{frontend}`.
**Why it happens:** Conflating per-file fallback with per-PR fallback.
**How to avoid:** `general` is a **PR-level** fallback (D-03): only when the whole PR matched zero real rules. Compute the union of real labels first; if it's empty, *then* set `{general}`. The example in Pattern 2 encodes this.
**Warning signs:** Mixed PRs tagged `general`; tests for "frontend + odd file" failing.

### Pitfall 4: Empty-PR skip vs general fallback confusion (D-10 vs D-02)
**What goes wrong:** A lockfile-only PR (all files filtered) routed to `general` and sent to the engine, burning tokens — instead of the neutral skip.
**Why it happens:** Both are "nothing to classify" states but have opposite outcomes.
**How to avoid:** Order matters. **Filter first.** If the kept-file list is empty → D-10 neutral skip (no engine call, sticky "no reviewable files (N filtered)"). Only if files remain do you classify, and only then can `general` fire.
**Warning signs:** Engine called on lockfile-only PR; "no reviewable files" note missing.

### Pitfall 5: `DiffBundle.files` order / determinism in the audit trail
**What goes wrong:** Label set rendered in nondeterministic order makes the sticky comment churn (edits in place on every run) and makes tests flaky.
**Why it happens:** Building labels from a set/dict without a stable sort.
**How to avoid:** Sort labels deterministically (e.g. alphabetical, or a fixed canonical order security→frontend→backend→data→infra→general) before rendering and before comparing in tests.
**Warning signs:** Snapshot tests flaky; sticky comment edited with no real change.

## Code Examples

### Default rules data file shape (D-04) — illustrative
```yaml
# src/prevue/classify/default_rules.yml  (built-in; consumer prevue.yml merges additively)
ignore:                       # DIFF-02 noise filters (D-07 additive base)
  - "**/*.lock"
  - "**/package-lock.json"
  - "**/yarn.lock"
  - "**/pnpm-lock.yaml"
  - "**/poetry.lock"
  - "**/uv.lock"
  - "**/Cargo.lock"
  - "**/*.min.js"
  - "**/*.min.css"
  - "**/dist/**"
  - "**/build/**"
  - "**/vendor/**"
  - "**/node_modules/**"
  - "**/*.png"
  - "**/*.jpg"
  - "**/*.gif"
  - "**/*.pdf"
  - "**/*.woff2"
labels:                       # CLSF-01 — glob -> one of the 5 categories
  frontend:
    - "**/*.tsx"
    - "**/*.jsx"
    - "**/*.vue"
    - "**/*.css"
    - "**/*.scss"
  backend:
    - "**/*.py"
    - "**/*.go"
    - "**/*.rb"
    - "**/*.java"
  infra:
    - "**/*.tf"
    - "terraform/**"
    - "**/Dockerfile"
    - "**/*.dockerfile"
    - ".github/workflows/**"
    - "**/k8s/**"
  data:
    - "**/migrations/**"
    - "**/*.sql"
    - "**/schema.prisma"
  security:
    - "**/auth/**"
    - "**/*.pem"
    - "**/.env*"
    - "**/secrets/**"
routing:                      # ROUT-01 / D-06 — 1:1 default, overridable
  # (empty => default 1:1 by name; consumer entries override)
```
> The exact glob set is **Claude's discretion** (D-noted). This shows shape and the additive `ignore`/`labels`/`routing` sections. Note a file can match multiple labels (D-01 union, e.g. `**/.env*` under both security and a filter) — design overlap deliberately. `[ASSUMED — default rule contents are a design choice, not a verified fact]`

### Inserting the stage in `run_review()` (D-08, D-10)
```python
# Source: existing src/prevue/review.py (Phase 1) + this phase's additions
def run_review(*, adapter: EngineAdapter | None = None) -> None:
    ctx = load_pr_context()
    if ctx.head_repo_full != ctx.base_repo_full:
        raise ForkPrUnsupported()

    diff = fetch_diff()
    ruleset = load_ruleset(ctx)                       # built-in + consumer (trusted base ref)

    reduced, dropped = filter_diff(diff, ruleset.ignore_globs)   # D-08

    pr = get_authenticated_pull(ctx)
    if not reduced.files:                             # D-10 neutral skip
        upsert_skip_note(pr, dropped_count=len(dropped))
        return

    result_labels = classify(reduced.files, ruleset.label_rules)  # CLSF-01, D-01/D-03
    bundle_ids = route(result_labels.keys(), ruleset.routing_map) # ROUT-01

    req = ReviewRequest(diff=reduced, instructions=BASELINE_INSTRUCTIONS,
                        budget_seconds=300, model=os.environ.get("COPILOT_MODEL"))
    result = (adapter or CopilotCliAdapter()).review(req)         # sees only filtered diff
    upsert_sticky(pr, result, classification=result_labels, bundles=bundle_ids)  # D-09
```

### Rendering the audit trail in Metadata (D-09)
```python
# Source: existing src/prevue/github/comments.py render_body (Phase 1 Metadata placeholder)
def _render_metadata(classification: dict[str, str], bundles: list[str]) -> str:
    # compact: labels + matched rule per label, not a per-file dump (D-09)
    labels_line = ", ".join(
        f"{label} (matched `{glob}`)" for label, glob in sorted(classification.items())
    )
    return (f"### Metadata\n"
            f"Labels: {labels_line}\n"
            f"Bundles: {', '.join(sorted(bundles))}\n")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pathspec.PathSpec.from_lines("gitwildmatch", ...)` | `pathspec.GitIgnoreSpec.from_lines(...)` | pathspec 1.x (factory "gitwildmatch" → "gitignore"; `GitIgnoreSpec` wrapper) | Old snippets break; use the new factory/class |
| `match_file()` only (boolean) | `check_file()` returning `CheckResult(file, include, index)` | pathspec recent 0.x → 1.x | Free matched-pattern provenance for audit trails — central to D-09 |

**Deprecated/outdated:**
- The `"gitwildmatch"` string factory name in 0.12-era tutorials — superseded; do not copy.

## Runtime State Inventory

> Phase 2 is a **greenfield additive code change** (new pure functions + one new YAML data file + edits to `review.py`/`comments.py`). It introduces no stored data, live-service config, OS registrations, or new secrets. The only new "build artifact" is the packaged `default_rules.yml`, which must be included in the wheel.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — stateless reusable-workflow design; no datastore | None |
| Live service config | None — no external service registers Phase 2 state | None |
| OS-registered state | None | None |
| Secrets/env vars | None new. Existing `COPILOT_GITHUB_TOKEN`/`COPILOT_MODEL` unchanged | None |
| Build artifacts | New `src/prevue/classify/default_rules.yml` must ship in the wheel | Verify `uv_build` includes non-`.py` package data; add a packaging test that `importlib.resources.files("prevue.classify")/"default_rules.yml"` resolves after build |

**Packaging note:** The `uv_build` backend (per pyproject.toml) generally includes files under the package dir, but **YAML data files are a classic "works in source, missing in wheel" trap.** The plan should include a verification step (build the wheel, install in a clean env, confirm the rules file loads via `importlib.resources`).

## Common Pitfalls (Quick Reference)

- pathspec factory rename → `GitIgnoreSpec.from_lines`
- gitignore dir-prefix over-match → use explicit `dir/**` and `/anchored`
- D-01 union vs D-03 general → general is PR-level only
- D-10 filter-first ordering → skip before classify
- deterministic label ordering → fixed canonical sort
- `yaml.safe_load` only
- package the YAML data file → wheel-inclusion test

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.* + pytest-cov 7.* (`[dependency-groups].dev` in pyproject.toml) `[VERIFIED: read pyproject.toml]` |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options] testpaths = ["tests"]` |
| Quick run command | `uv run pytest tests/test_classify_*.py -x -q` |
| Full suite command | `uv run pytest -q` |
| Mock approach | `responses` for GitHub REST (existing); classification/filter/route are pure → no mocks needed, just data fixtures |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIFF-02 | Lockfile/generated/vendored/binary + consumer-ignore globs dropped before classify | unit | `uv run pytest tests/test_classify_filter.py -x` | ❌ Wave 0 |
| DIFF-02 / D-08 | Engine receives reduced `DiffBundle` (filtered files absent) | unit | `uv run pytest tests/test_review_flow.py -k filtered -x` | ⚠️ extend existing |
| DIFF-02 / D-10 | All-filtered PR → neutral skip note, no engine call | unit | `uv run pytest tests/test_review_flow.py -k empty_skip -x` | ⚠️ extend existing |
| CLSF-01 | `.tsx`→frontend, `.tf`→infra, multi-domain PR → union of labels (D-01) | unit | `uv run pytest tests/test_classify_classifier.py -x` | ❌ Wave 0 |
| CLSF-01 / D-03 | PR with zero real-rule matches → `{general}`; mixed PR stays specific | unit | `uv run pytest tests/test_classify_classifier.py -k general -x` | ❌ Wave 0 |
| CLSF-03 | Rules load from YAML; consumer rules merge additively/override-by-label (D-05/D-07) | unit | `uv run pytest tests/test_classify_rules.py -x` | ❌ Wave 0 |
| CLSF-03 / D-09 | Matched-rule provenance (`check_file().index`) surfaced in audit output | unit | `uv run pytest tests/test_classify_classifier.py -k provenance -x` | ❌ Wave 0 |
| CLSF-03 / D-09 | Sticky Metadata renders labels + matched rule per label | unit | `uv run pytest tests/test_comments.py -k metadata -x` | ⚠️ extend existing |
| ROUT-01 | Labels → bundle ids 1:1 default; consumer override wins (precedence D-06) | unit | `uv run pytest tests/test_classify_router.py -x` | ❌ Wave 0 |
| (packaging) | `default_rules.yml` loads via `importlib.resources` after wheel build | integration | `uv run pytest tests/test_classify_rules.py -k packaged -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_classify_*.py -x -q`
- **Per wave merge:** `uv run pytest -q` (full suite green incl. Phase 1 regression)
- **Phase gate:** Full suite green + `uv run ruff check` clean before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_classify_filter.py` — DIFF-02 filter behavior, additive consumer ignores, dropped-count
- [ ] `tests/test_classify_classifier.py` — CLSF-01 label assignment, D-01 union, D-03 general, provenance
- [ ] `tests/test_classify_rules.py` — CLSF-03 YAML load + additive merge + packaged-resource load
- [ ] `tests/test_classify_router.py` — ROUT-01 routing map + precedence (D-06)
- [ ] Extend `tests/test_review_flow.py` — D-08 reduced bundle reaches engine; D-10 neutral skip branch
- [ ] Extend `tests/test_comments.py` — D-09 Metadata renders labels + matched rules
- [ ] Test data fixtures: sample `ChangedFile` lists per scenario (frontend-only, mixed, lockfile-only, no-match) — plain Python literals, no I/O

*Pure-function design means most tests are table-driven `(paths, ruleset) → expected labels` with zero mocking — ideal for TDD.*

## Security Domain

> `security_enforcement: true`, ASVS level 1. Phase 2 processes consumer-supplied config (`.github/prevue.yml`) and file paths — both are input-validation surfaces.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in this phase (GitHub token handled in Phase 1 I/O) |
| V3 Session Management | no | Stateless |
| V4 Access Control | yes (lightweight) | Consumer `prevue.yml` read from **trusted base ref only**, never from PR-modified files (SECR-01/WKFL-03 posture). Established Phase 1 pattern. |
| V5 Input Validation | **yes** | `yaml.safe_load` (never `yaml.load`); validate parsed config into pydantic `RuleSet` (reject malformed rules with a clear error, fail-closed per Phase 1 D-09); treat consumer globs as data, never as code |
| V6 Cryptography | no | No crypto |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| YAML deserialization → code execution | Tampering / Elevation | `yaml.safe_load` exclusively; pydantic validation of the result |
| Malicious consumer config from PR head (untrusted) | Tampering | Read `prevue.yml` from trusted base ref only — established posture; do not read from checkout of PR code |
| Crafted file path / glob causing pathological match (ReDoS-style) | DoS | pathspec compiles globs to bounded regex; cap rule count / path count if needed. Low risk — diffs are bounded by GitHub API page sizes |
| Misclassification hiding a sensitive file from review | Repudiation / Info | D-03 `general` fallback guarantees no file is silently un-reviewed; filtered files are disclosed (D-09 / D-10 "N filtered") |

> Note: the **security label** here is a classification category (route to the security skill bundle), not a security control. The actual "flag committed secrets" behavior lives in the Phase 3 security bundle (SKIL-02 note in REQUIREMENTS.md).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ (project floor 3.12) | 3.12+ | — |
| pathspec | filter + classify | ✗ not yet declared | install 1.1.* | none — required; add to pyproject |
| PyYAML | rule loading | ✗ not yet declared | install 6.0.* | none — required; add to pyproject |
| pydantic | models | ✓ | 2.13.* | — |
| pytest / pytest-cov / responses / ruff | tests + lint | ✓ (dev group) | per pyproject | — |

**Missing dependencies with no fallback:** `pathspec` and `PyYAML` are not in `pyproject.toml` yet — the first plan task must add them (`uv add "pathspec==1.1.*" "PyYAML==6.0.*"`). Pure code/config phase otherwise; no external services, no network at runtime beyond Phase 1's existing GitHub calls.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The specific default glob→label rule contents (which extensions/paths map to which of the 5 labels) | Code Examples §default rules | Low — explicitly Claude's discretion (D-noted); refine during planning/review. Wrong mappings misclassify but are trivially editable data |
| A2 | `uv_build` includes the `default_rules.yml` data file in the wheel without extra config | Runtime State Inventory | Medium — if excluded, classification fails at runtime in the packaged workflow. Mitigated by the explicit wheel-inclusion test in Wave 0 |
| A3 | Consumer `prevue.yml` schema (top-level `ignore`/`labels`/`routing` keys) | Patterns 3–4 | Low — internal schema, Claude's discretion; pydantic validation makes it explicit and testable |

**Verified (not assumed):** pathspec 1.1.1 + PyYAML 6.0.3 versions and Python floors (PyPI); `GitIgnoreSpec` API surface, `check_file()`→`CheckResult(file, include, index)`, gitignore dir-prefix / negation / anchoring / depth semantics (local execution); existing Phase 1 seam structure (`run_review`, `fetch_diff`, `DiffBundle`/`ChangedFile`, `comments.render_body` Metadata placeholder) (read source); pyproject.toml current deps (read source).

## Open Questions

1. **Should the classification result extend `DiffBundle`/`ChangedFile` or be a separate `ClassificationResult` model?**
   - What we know: It must thread from `run_review()` to `upsert_sticky()` (D-09) and onward to Phase 3 (bundle ids).
   - What's unclear: cleanest attachment point (Claude's discretion per CONTEXT).
   - Recommendation: a separate `ClassificationResult` pydantic model (labels: dict[str,str] of label→matched-glob, bundles: list[str], dropped_count: int) passed alongside the request — keeps `DiffBundle` a pure diff shape and gives Phase 3 a stable consumption surface.

2. **Where exactly does the consumer `.github/prevue.yml` come from in Phase 2?**
   - What we know: must be the trusted base ref (SECR-01/WKFL-03), not PR head.
   - What's unclear: Phase 2 runs before the full reusable-workflow packaging (Phase 5). In CI today there may be no consumer config to read.
   - Recommendation: implement the merge logic + load-from-path now, but make consumer config **optional** (absent → built-in rules only). Wire the actual trusted-base-ref fetch fully in Phase 5; Phase 2 can read from a local path / be tested with fixtures. Confirm with planner.

## Sources

### Primary (HIGH confidence)
- pathspec 1.1.1 — local execution of the actual wheel: `GitIgnoreSpec.from_lines`, `match_file`, `check_file` → `CheckResult(file, include, index)`, gitignore dir-prefix/negation/anchor/depth semantics (verified 2026-06-11)
- PyPI JSON API — pathspec latest 1.1.1 (published 2026-04-27, requires_python >=3.9); PyYAML latest 6.0.3 (requires_python >=3.8)
- pathspec PyPI project page (WebFetch) — repo github.com/cpburnz/python-pathspec, maintainer Caleb P. Burns, Production/Stable, dep of Black/pip/setuptools
- Project source (read): `src/prevue/{models,review,cli}.py`, `src/prevue/github/{diff,comments}.py`, `tests/{conftest,test_review_flow}.py`, `pyproject.toml`, `.planning/config.json`
- `.planning/research/STACK.md` — verified deps incl. pathspec 1.1.1 GitIgnoreSpec caveat, PyYAML 6.0.3
- `.planning/phases/02-.../02-CONTEXT.md` — locked decisions D-01..D-10

### Secondary (MEDIUM confidence)
- CLAUDE.md project tech stack table (pathspec/PyYAML/pydantic versions) — consistent with STACK.md and PyPI

### Tertiary (LOW confidence)
- Default rule-set glob contents (A1) — design choice, not externally verified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions live-verified on PyPI; API verified by executing the actual wheel
- Architecture: HIGH — slots into a read, well-defined Phase 1 seam; pure-function decomposition matches existing patterns
- Pitfalls: HIGH — pathspec semantics empirically verified (factory rename, dir-prefix, negation, anchoring)
- Default rules: LOW — explicitly Claude's discretion (A1)

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (stable libraries; pathspec/PyYAML release cadence is slow)
