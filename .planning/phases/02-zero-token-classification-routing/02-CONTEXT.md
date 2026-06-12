# Phase 2: Zero-Token Classification & Routing - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Deterministic classifier that turns a `DiffBundle`'s changed files into category
labels (security, frontend, backend, data, infra) and routes those labels to
skill-bundle identifiers — spending **zero LLM tokens**. Noise files are filtered
before classification, rules live in data (overridable by consumers), and the
label/rule decision trail is surfaced in the sticky comment's Metadata section.

Requirements: DIFF-02, CLSF-01, CLSF-03, ROUT-01.

**Explicitly later phases:** the cheap-LLM fallback for genuinely ambiguous diffs
(CLSF-02 → Phase 5), the actual SKILL.md bundles + loader (SKIL-01/02/04 → Phase 3),
inline comments / merge gate (Phase 4). Phase 2 emits bundle **identifiers**, not
loaded skills — the bundles don't exist yet.

</domain>

<decisions>
## Implementation Decisions

### Label assignment
- **D-01:** **Multi-label union.** A PR spanning domains (e.g. `.tsx` + Terraform)
  receives every matched label; downstream loads the union of matched bundles. No
  single-dominant-label tie-break — honors "load only what's needed" without
  under-reviewing a secondary domain.

### Unmatched-file fallback (the Phase 2↔5 seam)
- **D-02:** Files matching no deterministic rule fall back to a **`general`** label
  routing to a baseline/general bundle. Deterministic, zero-token, never leaves a
  file un-reviewed. Phase 5's LLM fallback later upgrades `general` → specific.
- **D-03:** **`general` fires only when NO file in the PR matched a real rule.** If
  any file got a real label, route to those bundles only and fold the unmatched
  file(s) into that review. A `.tsx` + one odd file stays frontend-only — keeps
  mixed PRs clean and avoids tagging nearly every PR `general`.

### Rules & routing config
- **D-04:** **Built-in default rules ship as a repo data file (YAML).** Glob→label
  rules are data, not code (CLSF-03).
- **D-05:** Consumer rules in `.github/prevue.yml` are **additive / override-by-label**
  (extend or override the built-in set; not a full replace).
- **D-06:** **label→bundle routing map defaults 1:1 by name, overridable.** Routing
  precedence (consumer override > consumer custom > built-in) is the contract for
  when bundles exist in Phase 3; Phase 2 only needs the overridable map.

### Path filtering
- **D-07:** Default noise filters (lockfiles, generated, vendored, binary) and
  consumer ignore globs are **additive** — consumer globs add to the built-ins
  (not replace).
- **D-08:** **Filtered files are dropped from BOTH classification and the review
  diff the engine sees.** Don't spend review tokens on lockfiles. (Modifies the
  `DiffBundle` before it reaches the engine — interacts with `run_review()`.)

### Audit trail
- **D-09:** Surface assigned labels + the matched rule per label in the sticky
  comment's **Metadata** section (the D-04 placeholder from Phase 1). Compact —
  labels + matched rule, not a full per-file dump.

### Empty-PR edge case
- **D-10:** A PR where ALL files are filtered out (e.g. lockfile-only) → **neutral
  skip**: no engine call, post a sticky note "no reviewable files (N filtered)".
  Zero tokens, honest disclosure (aligns with DIFF-02). Not an error, not a
  `general` review.

### Claude's Discretion
- Classifier module layout, rule-data file path/schema, and the glob-matching
  implementation. STACK.md recommends **pathspec 1.1.1** (`GitIgnoreSpec`) for
  git-exact `**` semantics and **PyYAML 6.0.3** for config parsing — planner should
  honor these unless a better fit emerges. Note pathspec 1.x renamed the pattern
  factory ("gitwildmatch" → "gitignore"); don't copy 0.12-era snippets.
- How labels/rules attach to the existing pydantic models (extend `DiffBundle`/
  `ChangedFile` vs a new classification result model).
- Default rule set contents (which globs → which of the 5 labels).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Stack & platform facts
- `.planning/research/STACK.md` — verified deps for this phase: **pathspec 1.1.1**
  (gitignore-style glob matching, `GitIgnoreSpec.from_lines([...]).match_file(path)`;
  1.x factory rename caveat), **PyYAML 6.0.3** (parse `.github/prevue.yml`; already a
  transitive dep — don't add a second YAML lib), **python-frontmatter 1.3.0** (for
  later SKILL.md, not this phase). Also the "What NOT to Use" note: never `fnmatch`/
  `pathlib.match` for `**` semantics — they misclassify silently.

### Project specs
- `.planning/PROJECT.md` — pipeline definition (classify → route → load), hybrid
  deterministic-first constraint, key decisions.
- `.planning/REQUIREMENTS.md` — DIFF-02, CLSF-01, CLSF-03, ROUT-01 definitions; the
  out-of-scope table (LLM-only classification is explicitly rejected).
- `.planning/phases/01-walking-skeleton-review-loop/01-CONTEXT.md` — Phase 1
  decisions this phase builds on: D-04 sticky-comment sectioned shell (Metadata
  placeholder lives here), D-07 no PR title/body in prompts, D-09 fail-closed.

### Existing code (Phase 1)
- `src/prevue/models.py` — `DiffBundle`, `ChangedFile`, `ReviewRequest` pydantic
  contract. Classification consumes `ChangedFile.path`/`status`; filtering modifies
  `DiffBundle.files`.
- `src/prevue/github/diff.py` — `fetch_diff()` builds the `DiffBundle`; classification/
  filtering slots between fetch and engine.
- `src/prevue/review.py` — `run_review()` orchestration; filter→classify→route inserts
  here, before `engine.review(req)`; empty-PR neutral skip (D-10) handled here.
- `src/prevue/github/comments.py` — `upsert_sticky()`; Metadata audit trail (D-09)
  rendered here.

No external ADRs — greenfield repo; decisions captured above + in REQUIREMENTS.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DiffBundle` / `ChangedFile` (pydantic, `models.py`) — classification input;
  `ChangedFile.path` + `.status` are the deterministic signal. Filtering = produce a
  reduced `DiffBundle.files`.
- `run_review()` (`review.py`) — single orchestration seam; the new
  filter→classify→route stage inserts between `fetch_diff()` and `engine.review()`.
- Sticky comment Metadata section (`comments.py`, D-04 from Phase 1) — already a
  placeholder; the audit trail (D-09) fills it.

### Established Patterns
- pydantic models for every system-boundary data shape (STACK.md pattern; Phase 1
  locked it). New classification/routing result should follow suit.
- Config read from the **trusted base ref** only (WKFL-03, SECR-01 posture) — consumer
  `prevue.yml` rules are not taken from PR-modified files.
- Data-as-rules: deterministic, debuggable, auditable (PROJECT.md rejects non-
  deterministic routing).

### Integration Points
- `fetch_diff()` → **[new: filter + classify + route]** → `ReviewRequest` → engine.
- Routing output (label set + bundle identifiers) must thread through to where Phase 3
  loads bundles — keep the result on/alongside the request so Phase 3 can consume it.
- Audit data threads to `upsert_sticky()` Metadata.

</code_context>

<specifics>
## Specific Ideas

- Token-thesis fidelity is the through-line: filtered files cost zero engine tokens
  (D-08), `general` only when truly unclassified (D-03), empty PRs skip the engine
  entirely (D-10). Every decision defends "don't spend tokens on what the PR doesn't
  need."
- The `general` label is the deliberate, named hand-off point to Phase 5's LLM
  fallback — plan it as an explicit seam, not an afterthought.

</specifics>

<deferred>
## Deferred Ideas

- **LLM fallback classification** (→ Phase 5, CLSF-02): upgrade `general`-labeled /
  ambiguous PRs via a cheap LLM call. Phase 2 only provides the deterministic seam
  (the `general` label). Compose that prompt from diff hunks + PR summary as quoted
  *data* (carried from Phase 1 deferred; interacts with SECR-02).
- **Skill bundle loading + the 5 built-in SKILL.md bundles** (→ Phase 3,
  SKIL-01/02/04): Phase 2 emits bundle identifiers only; loading from trusted ref is
  Phase 3.
- **Inline comments / merge gate** (→ Phase 4): routing/labels feed severity + gating
  later; not here.

None of the above is scope creep into Phase 2 — discussion stayed within the
classify-and-route boundary.

</deferred>

---

*Phase: 2-Zero-Token Classification & Routing*
*Context gathered: 2026-06-11*
