# Phase 3: Selective Skill Loading - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

A skill **loader** that turns Phase 2's classification output into the engine's
review context: it scans the framework's built-in skill files, selects exactly
the skills whose `applies-to` globs match the PR's (already-filtered) changed
files, assembles their bodies into `ReviewRequest.instructions`, and surfaces
which skills loaded in the sticky-comment audit trail.

Five built-in bundles ship as markdown (security, frontend, backend, data, infra),
each a directory of single-skill files. Selection is **per-skill and
deterministic** (glob match, zero LLM tokens). Skills load only from the trusted
framework checkout — never from PR-modified files.

Requirements: SKIL-01 (load only matched skills), SKIL-02 (5 built-in bundles),
SKIL-04 (trusted-ref-only).

**Explicitly later phases:** consumer custom skills + override of built-ins via
`.github/prevue/skills/` and real base-ref git resolution (SKIL-03 → Phase 6);
LLM upgrade of the `general`/no-match seam (CLSF-02 → Phase 5); structured
findings, inline comments, merge gate (Phase 4); token-budget packing + loaded-vs-
skipped token transparency (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### Bundle & skill layout
- **D-01:** **Bundle = directory of single-skill markdown files.** Layout
  `src/prevue/skills/<bundle>/<skill>.md` (e.g. `skills/backend/error-handling.md`).
  One skill per file — modular, individually addressable, room to grow. Rejected:
  monolithic SKILL.md per bundle (can only load whole), single rules-style data
  file (breaks SKILL.md/Agent-Skills portability the project committed to).
- **D-02:** **Skill frontmatter = `name` + `description` + `applies-to` (globs).**
  No `label`/bundle key in skill frontmatter — the bundle is the directory; routing
  semantics live in Phase 2's `routing_map`. Avoids redundant per-skill routing
  metadata that drifts.

### Selection granularity (the core decision)
- **D-03:** **Per-skill deterministic selection via `applies-to` globs**, reusing
  Phase 2's pathspec engine. A skill loads only when the PR's changed-file paths
  match its globs — across any bundle. Maximum precision / true "load only what's
  needed" (a backend PR loads only the backend skills whose globs actually match,
  not the whole backend bundle).
- **D-04:** **Skill globs are the primary load selector; bundles organize + carry
  audit/override semantics, NOT a load gate.** Loader scans all skill files and
  loads any whose globs match — regardless of which bundles Phase 2 routed. Phase
  2's `bundles` output stays meaningful for the audit Metadata (D-09), the
  `general` seam, and Phase 6 override precedence. Rejected: two-stage bundle-gate-
  then-skill-filter (gate is redundant once skill globs exist and can't load a
  relevant skill from a non-routed bundle).

### Phase 2 relationship (no rework)
- **D-05:** **Phase 3 layers on Phase 2; it does NOT revise or override it.** Phase
  2's file→label→`bundles` classifier and its sticky-Metadata audit stay correct
  and unchanged. The only overlap — both stages run pathspec globs over changed
  files — is acceptable layering (different questions: "what domains" vs "which
  skills") and the planner **reuses Phase 2's pathspec helper** (DRY at the helper
  level, no duplicated logic).

### No-match fallback (the `general` seam realized)
- **D-06:** **No skill's globs match → fall back to `BASELINE_INSTRUCTIONS` alone.**
  This is Phase 3's realization of Phase 2's D-02/D-03 `general` seam: never leave a
  PR un-reviewed, no 6th `general` bundle (SKIL-02 lists only 5). Rejected: dedicated
  general bundle (extra content), always-load-baseline-skill (every review carries
  baseline tokens — tension with token thesis).

### Context assembly
- **D-07:** **Baseline preamble + delimited skill sections.** `BASELINE_INSTRUCTIONS`
  stays as a short reviewer-role preamble; each matched skill body appended under a
  clear delimiter/header (e.g. `## Skill: <name>`). Engine sees role framing +
  specialist guidance.
- **D-08:** **Deterministic skill order: Phase 2 `CANONICAL_LABEL_ORDER` of the
  skill's bundle (security→frontend→backend→data→infra), then filename
  alphabetically.** Security-first, reproducible (snapshot-test friendly). Rejected:
  filesystem match order (non-deterministic), per-skill `priority` key (over-
  engineered for v1).
- **D-09:** **Dedupe loaded skills by file path — each skill loads at most once**
  even if multiple of its globs match. Mirrors Phase 2 router dedupe (WR-02); no
  repeated guidance / wasted tokens.

### Trusted-ref scope (SKIL-04)
- **D-10:** **SKIL-04 satisfied by construction; assert the invariant, defer the
  machinery.** Built-in skills ship inside the framework repo — part of the checked-
  out Prevue code, not the PR under review (which lives in a different repo), so they
  are inherently trusted. Encode it: **load only from the fixed framework `skills/`
  dir**, add a test/assert that the load path is the framework dir, document the
  invariant. Real base-ref git resolution (reading consumer skills from a resolved
  trusted ref) deferred to Phase 5/6 when consumer skills exist.

### Skill content depth
- **D-11:** **Real but lean checklists.** Each bundle ships a handful of genuine
  review-guidance skills (lean but actually useful — proves the thesis that
  specialist skills add depth), not thin placeholders. **Security bundle MUST include
  a skill that flags secrets/credentials committed in the diff — alert, not redact**
  (SKIL-02 note, carried from Phase 1 discussion).

### Robustness
- **D-12:** **Fail-closed on malformed/missing skill frontmatter.** A built-in skill
  with invalid frontmatter (e.g. no `applies-to`) is a framework bug, not a runtime
  PR condition — validate all skill frontmatter on load and raise so CI/tests catch
  it; never silently skip. Matches Phase 1 D-09 fail-closed posture.

### Audit trail
- **D-13:** **Surface loaded skill names + their bundles in the sticky-comment
  Metadata**, extending the Phase 2 D-09 section (alongside existing labels/rules).
  Proves "loaded only what was needed" (the token thesis) and sets up Phase 6's
  loaded-vs-skipped transparency.

### Claude's Discretion
- Loader module layout/path; exact frontmatter parser (STACK recommends
  **python-frontmatter 1.3.0**; planner should honor unless a better fit emerges).
- Exact delimiter/templating string for assembled skill sections (D-07 fixes the
  shape, not the literal markup).
- The actual default skill content per bundle (D-11 fixes depth + the security
  secrets requirement; researcher may draft from review best practices).
- Whether skill frontmatter validation is a pydantic model vs manual check (D-12
  fixes fail-closed behavior, not mechanism).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Stack & platform facts
- `.planning/research/STACK.md` — verified deps for this phase: **python-frontmatter
  1.3.0** (`frontmatter.load(path)` → metadata dict + body; SKILL.md frontmatter
  format), **pathspec 1.1.1** (`GitIgnoreSpec.from_lines([...]).match_file(path)` for
  per-skill `applies-to` globs — same engine Phase 2 uses; reuse the helper). Also
  the agentskills.io SKILL.md frontmatter schema (name/description required + optional
  metadata map) and the "What NOT to Use" note: never invent a custom skill format —
  Agent Skills is an open multi-vendor standard.

### Project specs
- `.planning/PROJECT.md` — pipeline definition (classify → route → **load** →
  review), token-efficiency thesis, bundled-skillset model (Agent Skills / SKILL.md
  convention).
- `.planning/REQUIREMENTS.md` — SKIL-01, SKIL-02 (incl. the security secrets-flagging
  note), SKIL-04 definitions; out-of-scope table (no remote skill registry — built-in
  + consumer-local only).
- `.planning/phases/02-zero-token-classification-routing/02-CONTEXT.md` — Phase 2
  decisions this phase builds on: D-06 routing precedence contract, the `general`
  label seam (D-02/D-03), `bundles` emitted as identifiers awaiting this loader.
- `.planning/phases/01-walking-skeleton-review-loop/01-CONTEXT.md` — Phase 1
  decisions: sticky-comment sectioned Metadata, D-09 fail-closed posture.

### Existing code (Phase 1 + 2)
- `src/prevue/classify/router.py` — `route()` produces `ClassificationResult.bundles`
  (ordered, deduped bundle ids). The loader consumes the classification result; the
  pathspec/canonical-order patterns here are the ones to reuse.
- `src/prevue/classify/models.py` — `CANONICAL_LABEL_ORDER` (skill ordering, D-08),
  `ClassificationResult` (labels/bundles/dropped_count — extend or read for skill
  audit, D-13).
- `src/prevue/classify/classifier.py` / `filter.py` — the pathspec glob-matching
  engine to reuse for per-skill `applies-to` matching (D-03/D-05).
- `src/prevue/review.py` — `run_review()` orchestration. Loader inserts after
  `route()` and before building `ReviewRequest`; replaces the hardcoded
  `BASELINE_INSTRUCTIONS` arg with the assembled instructions (D-06/D-07). No-match
  fallback (D-06) handled here.
- `src/prevue/models.py` — `ReviewRequest.instructions` is the injection target.
- `src/prevue/github/comments.py` — `upsert_sticky()` Metadata; D-13 adds loaded-skill
  names to the existing D-09 audit section.
- `src/prevue/classify/default_rules.yml` — reference for the data-as-files,
  glob-authoring style the skill `applies-to` globs should mirror.

No external ADRs — greenfield repo; decisions captured above + in REQUIREMENTS.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Pathspec glob engine** (`classify/classifier.py`, `filter.py`) — Phase 2's
  `GitIgnoreSpec` matching is reused verbatim for per-skill `applies-to` globs (D-05).
  Do NOT re-implement glob matching.
- **`CANONICAL_LABEL_ORDER`** (`classify/models.py`) — drives deterministic skill
  ordering (D-08).
- **Router dedupe pattern** (`router.py`, seen→append) — mirror it for skill dedupe
  by path (D-09).
- **Sticky Metadata section** (`comments.py`, D-09 from Phase 2) — already renders
  labels/rules; extend with loaded skill names (D-13).
- **`run_review()` seam** (`review.py`) — single orchestration point; loader slots
  between `route()` and `ReviewRequest` construction.

### Established Patterns
- pydantic models for every system-boundary shape (Phase 1/2 locked it) — skill model
  (name/description/applies-to) should follow; supports D-12 fail-closed validation.
- Data-as-files, deterministic + auditable (PROJECT.md rejects non-deterministic
  routing) — per-skill globs continue this.
- Config/skills from the **trusted base ref only** (SECR-01/WKFL-03 posture) — D-10
  encodes the fixed-framework-dir load path now; real ref resolution is Phase 5/6.
- Fail-closed default (Phase 1 D-09) — D-12 applies it to malformed skills.

### Integration Points
- `route()` → **[new: scan skills → per-skill glob match → dedupe → order → assemble]**
  → `ReviewRequest.instructions` → engine.
- Loaded-skill list threads to `upsert_sticky()` Metadata (D-13), alongside Phase 2's
  labels/bundles.
- No-match path (D-06) returns `BASELINE_INSTRUCTIONS` unchanged — preserves the
  Phase 2 `general` seam without a `general` bundle.

</code_context>

<specifics>
## Specific Ideas

- **Skill-level selectivity is the phase's signature.** The roadmap criterion says
  "backend-only PR gets the backend bundle"; the user pushed finer — load only the
  *individual skills* (across bundles) whose globs match. The phase delivers more
  precision than the roadmap floor, deliberately. The token thesis is the through-
  line: every layer (per-skill globs D-03, no-match→baseline D-06, dedupe D-09) defends
  "don't put a skill in context the PR doesn't need."
- **Bundles don't disappear** — they remain the organizing unit, the audit grouping,
  and (Phase 6) the override/precedence unit. They're just not the *load* gate.
- **Security secrets-flagging is a hard content requirement** (D-11), not optional
  polish — carried from Phase 1.

</specifics>

<deferred>
## Deferred Ideas

- **Consumer custom skills + built-in override** via `.github/prevue/skills/`
  (→ Phase 6, SKIL-03): Phase 3 ships only built-in framework skills. Bundle-level
  override precedence (consumer override > consumer custom > built-in) is the Phase 2
  contract; Phase 6 wires it.
- **Real trusted-base-ref git resolution** (→ Phase 5/6): reading consumer skills from
  a resolved base ref. Phase 3 only needs the fixed-framework-dir load path + asserted
  invariant (D-10) because no PR-modifiable skills exist yet.
- **LLM upgrade of the no-match/`general` seam** (→ Phase 5, CLSF-02): when zero skills
  match, a cheap LLM pass could pick skills. Phase 3 deterministically falls back to
  baseline (D-06).
- **Token-budget packing + loaded-vs-skipped token transparency** (→ Phase 6): Phase 3
  surfaces *which* skills loaded (D-13) but not token accounting or budget-bounded
  packing.

None of the above is scope creep into Phase 3 — discussion stayed within the
load-matched-skills boundary.

</deferred>

---

*Phase: 3-Selective Skill Loading*
*Context gathered: 2026-06-12*
