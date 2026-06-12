# Phase 3: Selective Skill Loading - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-12
**Phase:** 3-selective-skill-loading
**Areas discussed:** Bundle layout & metadata, Selection granularity, Phase 2 relationship, Context assembly, general/no-match fallback, Trusted-ref scope, Skill content depth, Robustness (malformed skills / audit / dedupe)

---

## Bundle layout

| Option | Description | Selected |
|--------|-------------|----------|
| Dir-per-bundle SKILL.md | One SKILL.md per bundle dir (Agent Skills) | |
| Flat SKILL files | One file per bundle | |
| Single rules-style data file | All bundles in one YAML/markdown | |

**User's choice:** Dir-per-bundle direction, but raised that a bundle may hold **multiple** skills and each markdown file should contain a **single** skill only → evolved into "bundle = directory of single-skill files" (D-01).
**Notes:** Drove the layout `src/prevue/skills/<bundle>/<skill>.md`.

---

## Selection granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Per-skill deterministic match | Skill `applies-to` globs; load only matching skills across bundles | ✓ |
| Bundle granularity | Load whole matched bundle | |
| Hybrid: bundle default + per-skill opt-out | Load bundle, skills can opt out | |

**User's choice:** Per-skill deterministic match. User noted: "we may just need to load a couple of skills in a bundle and others in another bundle" — finer than the roadmap's bundle-level floor.
**Notes:** Flat single-skill-file layout (D-01) is what makes skills independently addressable for this.

### Skill match signal

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse classifier-style globs per skill | `applies-to` globs via Phase 2 pathspec engine | ✓ |
| Keyword/label tags per skill | Finer labels, more coupling | |
| Defer signal design to research | Lock intent only | |

**User's choice:** Reuse classifier-style globs (D-02/D-03). Resolved the deferred frontmatter question → `name` + `description` + `applies-to`.

---

## Phase 2 relationship

| Option | Description | Selected |
|--------|-------------|----------|
| Skill globs primary; bundles organize | Loader scans all skills, globs select; bundles = audit/override unit | ✓ |
| Two-stage: bundle gate then skill filter | Bundles prune dirs first | |

**User's choice:** Skill globs primary (D-04). User asked whether Phase 2 needs revision or gets overridden → answered: **no rework**, Phase 3 layers on top; Phase 2 output stays for audit/seam/override (D-05). Pathspec helper reused (DRY).

---

## Context assembly

| Option | Description | Selected |
|--------|-------------|----------|
| Baseline preamble + delimited skill sections | Baseline role + `## Skill:` sections | ✓ |
| Skills only, no baseline (when matches exist) | Skills replace baseline | |
| Defer assembly format to planner | Lock intent only | |

**User's choice:** Baseline preamble + delimited sections (D-07).

### Skill order

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical bundle order, then filename | `CANONICAL_LABEL_ORDER` then alpha | ✓ |
| Match order (as discovered) | Filesystem scan order | |
| Severity/priority frontmatter key | Per-skill priority | |

**User's choice:** Canonical bundle order then filename (D-08).

---

## general / no-match fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Fall back to BASELINE_INSTRUCTIONS | No 6th bundle; baseline when nothing matches | ✓ |
| Dedicated general bundle of skills | 6th bundle | |
| Always load a baseline skill + matches | Baseline floor every review | |

**User's choice:** Fall back to BASELINE_INSTRUCTIONS (D-06) — realizes Phase 2's `general` seam without a 6th bundle.

---

## Trusted-ref scope (SKIL-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Satisfied by construction + assert the invariant | Fixed framework `skills/` load path + test; defer git ref resolution | ✓ |
| Build base-ref git resolution now | Implement `git show base:path` | |
| Defer SKIL-04 entirely to Phase 6 | No guard | |

**User's choice:** Satisfied by construction + assert invariant (D-10).

---

## Skill content depth

| Option | Description | Selected |
|--------|-------------|----------|
| Real but lean checklists | Genuine guidance per bundle; security flags committed secrets | ✓ |
| Minimal placeholders | Thin proof-of-loading skills | |
| Defer content authoring to research/planner | Lock structure only | |

**User's choice:** Real but lean checklists (D-11). Security secrets-flagging is a hard requirement (SKIL-02 note).

---

## Robustness — malformed skills / audit / dedupe

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-closed at startup (malformed skill) | Validate frontmatter, raise on invalid | ✓ |
| Skip the bad skill + warn | | |
| Defer validation to planner | | |
| List loaded skill names + matched bundles (audit) | Extend D-09 Metadata with skills | ✓ |
| Bundle-level audit only | | |
| Defer Metadata format | | |
| Load each skill at most once (dedupe) | Dedupe by file path, mirror WR-02 | ✓ |
| No dedupe needed | | |

**User's choice:** Fail-closed (D-12), skill-name audit (D-13), dedupe by path (D-09).

---

## Claude's Discretion

- Loader module layout/path; frontmatter parser (python-frontmatter recommended).
- Exact delimiter/templating markup for assembled skill sections.
- Default skill content per bundle (depth + security requirement fixed).
- Skill-frontmatter validation mechanism (pydantic vs manual) — fail-closed behavior fixed.

## Deferred Ideas

- Consumer custom skills + built-in override via `.github/prevue/skills/` (→ Phase 6, SKIL-03).
- Real trusted-base-ref git resolution (→ Phase 5/6).
- LLM upgrade of the no-match/`general` seam (→ Phase 5, CLSF-02).
- Token-budget packing + loaded-vs-skipped token transparency (→ Phase 6).
