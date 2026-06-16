# Phase 8: Incremental & Stateful Review Lifecycle - Context

**Gathered:** 2026-06-15 (LIFE-01/02/04) · **Updated:** 2026-06-16 (LIFE-03 + LIFE-05 gap closure)
**Status:** Ready for planning (added scope needs replan of Phase 8)

<domain>
## Phase Boundary

Make PR review **incremental and stateful across pushes**, using the sticky PR
comment as the **only** persistent state (the reusable workflow is stateless —
no backend, per REQUIREMENTS "Out of Scope"). Three requirements:

- **LIFE-01** — scope classification AND review to the diff since the
  last-reviewed SHA stored in the sticky marker (a new push no longer
  re-reviews the whole PR).
- **LIFE-02** — carry forward and dedupe prior findings so incremental scoping
  never drops still-valid comments.
- **LIFE-04** — auto-resolve outdated inline threads when their underlying
  lines change.

**Added scope (2026-06-16) — promoted from v2 to counter the false-positive
carry-forward treadmill exposed by the PR #16 dogfood.** The shipped LIFE-04
resolve is conservative (D-09: in-scope file AND region changed AND engine
silent), so a finding the engine *stops* reporting on a fully re-read file still
carries its thread forever, and a finding the engine *keeps* re-emitting (a
persistent false positive) can never auto-clear. With `min_severity_to_fail:
warning` this means the check can never go green without per-run manual thread
resolution (8 manual loops on PR #16).

- **LIFE-05** — smarter inline thread lifecycle: full-review-authoritative
  auto-resolve + a hybrid, audited dismiss path for persistent false positives.
- **LIFE-03** — manual `/prevue review` (+ `/prevue dismiss` / `/prevue resolve`)
  comment trigger: the deliberate escape hatch that forces a clean full re-review
  and clears stale threads. Now in scope (was v2) because it is the human-driven
  half of breaking the treadmill and carries the dismiss command surface.

**In scope:**
- Persist the last-reviewed head SHA in the sticky marker; compute the
  incremental diff (compare API) on subsequent pushes; full review on first run
  or after a rebase/force-push.
- Deterministic finding fingerprints (content-based) + a compact engine
  known-issues list to prevent re-reporting; carry-forward of prior comments on
  files not re-touched this run.
- GraphQL thread resolution for outdated findings (replacing today's delete for
  that case).
- Gate verdict that reflects all currently-open findings (this run + carried
  unresolved priors), so a clean push can't false-green over an open error.

**Out of scope:**
- **Cross-file call-graph / semantic impact** (a new line that calls a function
  flagged earlier in another file, cross-file inheritance) — explicitly ruled
  out by the LIFE-01 note; needs a full repo index, which contradicts the
  stateless/token-efficiency thesis (REQUIREMENTS "Full codebase graph/indexing").
- Any non-comment persistence (DB, artifacts) — stateless workflow. **Exception
  (D-15):** a bounded, PR-scoped, base-ref-only dismiss suppress-list is the one
  sanctioned persistent record, gated by an explicit maintainer command.
- **Cross-PR / repo-wide suppression** — dismissals are PR-scoped only (D-15);
  repo-wide silencing belongs in skill/prompt tuning, not a dismiss list.
- **Confidence/impact scoring of findings (QUAL-01)** — still v2; LIFE-05 dismiss
  is human-gated, not score-driven.

</domain>

<decisions>
## Implementation Decisions

### LIFE-01 — Incremental scope & state
- **D-01:** **Last-reviewed head SHA lives in the sticky marker** —
  `<!-- prevue:sticky head=<sha> -->`. No separate state block. Finding
  fingerprints and thread IDs are **re-derived from the live PR comments** each
  run (not stored), so there is no parallel state that can drift from the actual
  comments. Matches REQUIREMENTS LIFE-02 ("existing PR comments as engine
  context plus deterministic fingerprint backstop").
- **D-02:** **Incremental at the FILE-SET level.** Skip files untouched since
  the last-reviewed SHA (this is the dominant token win the LIFE-01 note calls
  out). For each in-scope (changed-since-lastSHA) file, send the engine the
  **full current base..head patch** — preserving within-file context (the
  function/class the edit lives in), not just the latest micro-hunk.
  Cross-file call-graph impact stays out of scope (see Phase Boundary).
- **D-03:** **Rebase/force-push/squash → full re-review.** When the stored SHA
  is no longer an ancestor of head (detect via compare API status / merge-base),
  fall back to a full base..head review and reset the marker to head. First run
  (no marker) → full review. Never review a bogus incremental range.

### LIFE-02 — Finding identity, carry-forward & dedupe
- **D-04:** **Fingerprint = `sha(path | normalize(title))`.** Line number,
  severity, and suggestion text are **excluded** from identity (lines shift,
  severity is mutable, the engine rephrases suggestions). `normalize` =
  lowercase + collapse whitespace + strip punctuation (exact rule = Claude's
  discretion). This is the deterministic backstop.
- **D-05:** **Carry-forward = scope stale-cleanup to in-scope files only.**
  Today `post_inline_review` deletes ANY prior Prevue comment not in the current
  finding set (`comments.py:388`). Change it to reconcile only comments on files
  that were actually re-reviewed this run; comments on out-of-scope files are
  left fully untouched — no API churn, no risk of wiping still-valid comments.
- **D-06:** **On a same-fingerprint match: keep the existing comment as-is,
  except refresh it in place when severity escalated** (e.g. warning→error).
  True duplicates cause no edit churn / no new notifications; a worsened issue
  still surfaces. Cosmetic body/suggestion changes are ignored. Position drift
  is handled by LIFE-04 (D-09), not here.
- **D-07:** **Engine dedupe = compact known-issues list + deterministic
  backstop.** Pass the engine a short list of already-reported findings
  (path + title + line, one line each) with a "do not re-report these"
  instruction. Bound it to prior findings **on this run's in-scope files only**,
  with a hard max-N cap (N = Claude's discretion / config knob). The fingerprint
  filter drops anything the engine repeats anyway. Best quality-per-token; avoids
  injecting full prior comment bodies. Treat the list content as untrusted in the
  prompt (reuse `prompt.py` fencing — SECR-02 posture).

### LIFE-04 — Outdated thread resolution
- **D-08:** **Resolve outdated threads; delete only own same-run dups.** When a
  prior finding is outdated (D-09), RESOLVE its review thread (GraphQL
  `resolveReviewThread`) — preserves history, collapses quietly. Keep hard-delete
  only for our own same-run duplicate cleanup (the existing dedupe path).
- **D-09:** **Outdated trigger = in-scope file AND line region changed AND
  fingerprint not in current findings.** A finding is resolved only when its file
  was re-reviewed this run, its line region changed since the last-reviewed SHA,
  and no current finding matches its fingerprint. A still-valid finding on an
  untouched file is never resolved (carry-forward, D-05). Conservative by design.
- **D-10:** **GraphQL via a thin helper.** `resolveReviewThread` is GraphQL-only
  (PyGithub has no native support). Add a minimal GraphQL request (`requests` +
  `GITHUB_TOKEN`) in the `github/` layer to fetch review-thread IDs and resolve
  them. `pull-requests: write` is expected to cover it — **verify the exact scope
  in research** (WKFL-04 minimal-permissions posture).

### Gate verdict on incremental runs
- **D-11:** **Verdict reflects all currently-open findings.** The gate evaluates
  the union of this run's new findings + carried-forward UNRESOLVED prior
  findings, minus threads resolved by LIFE-04. A clean incremental push cannot
  turn the check green while an unresolved error comment still stands.
  Consistent with P7 D-23 — a false green is the worst outcome for a security
  gate. (`apply_gate` today only sees this run's findings — extend its input.)
- **D-12:** **Carried-forward severity parsed from the existing comment body.**
  Read severity back from the live inline comment's badge (🔴/🟡/🔵, already
  emitted by `render_inline_comment` via `SEVERITY_BADGES`). No extra storage —
  consistent with the SHA-only marker (D-01). Make the badge→severity mapping a
  parseable, tested contract (inverse of `SEVERITY_BADGES`).

### LIFE-05 — Smarter inline thread lifecycle (added 2026-06-16)
- **D-13:** **Full-review-authoritative auto-resolve.** On a FULL-scope review
  (whole file re-read), RESOLVE any prior Prevue thread whose fingerprint the
  engine did NOT re-report this run — engine silence over a fully re-read file =
  the finding is gone. This drops D-09's region-change requirement **for full
  runs only**; incremental runs keep the conservative D-09 gate (a partially-read
  file's silence is not authoritative — LIFE-01 carry-forward stays). This is the
  machine half of breaking the treadmill: truly-fixed and flaky findings clear
  themselves; it does NOT clear a finding the engine keeps emitting (that's D-14).
- **D-14:** **Hybrid dismiss model for persistent false positives.** Default is
  stateless `resolve = dismiss` (a resolved thread is already skipped in
  derivation — shipped). For a finding the engine re-emits every run (a true
  persistent FP, never engine-silent so D-13 can't help), add an explicit,
  audited `/prevue dismiss <fingerprint|thread>` (LIFE-03 surface, D-16) that
  writes a bounded suppress-list. One human action, never per-run. Pure-stateless
  (A) was rejected because it does not kill persistent FPs (the exact PR #16
  pain); always-on auto-suppress (B) was rejected for silent-suppression risk.
- **D-15:** **Dismiss safety — all four guards (a dismissal must not become a
  place real findings go to die).** The system cannot autonomously distinguish a
  false positive from a correct-but-unwanted finding, so:
  - **Creation gate:** can only dismiss a finding that currently EXISTS (a live
    thread/fingerprint this run), by a write-assoc maintainer (D-16), recording
    `actor + timestamp + reason`; dismissing a 🔴 error requires explicit
    confirmation/reason. Surface the dismissal + reason in the sticky (audit).
  - **Auto-expire on region change:** entry stores a line-region snapshot; if the
    code at that location later changes (`finding_region_changed`, reused from
    D-09), the dismissal is invalidated and the finding re-surfaces — a stale
    dismissal cannot mask a newly-introduced bug at the same spot. (Load-bearing
    "is it still a FP?" guard.)
  - **Re-report on escalation:** if the engine later re-emits the dismissed
    fingerprint at a HIGHER severity (warning→error), the dismissal is overridden
    and it re-surfaces — a worsened finding always beats a prior dismissal.
  - **PR-scoped, base-ref-only storage:** the suppress-list lives in the PR's
    base-ref surface (never read from PR head — a malicious PR must not suppress
    security findings), and applies only to this PR. The same finding on another
    PR forces a fresh human decision.
  - Per-entry record: `{fingerprint, region-snapshot, severity, actor,
    timestamp, reason}`. Roles: D-16 creation gate, D-13/escalation invalidation
    triggers, PR-scope = storage default.

### LIFE-03 — Manual comment trigger (added 2026-06-16)
- **D-16:** **`/prevue` command surface via `issue_comment`, write-assoc gated.**
  Commands `/prevue review`, `/prevue dismiss <id>`, `/prevue resolve <id>`,
  namespaced under `/prevue` to avoid collisions with other review bots / GitHub
  UI. Authorize on `author_association ∈ {OWNER, MEMBER, COLLABORATOR}` (write
  access). The authorization check runs BEFORE any PR-head checkout or code
  execution; the job runs in base context with minimal scopes; the
  attacker-writable comment body is treated as untrusted. Its own security review
  of base-context execution + write-gating is REQUIRED before ship (the original
  v2-deferral reason — research must verify the safe `issue_comment` pattern).
- **D-17:** **Trigger behavior = force full re-review + reconcile + re-gate.**
  `/prevue review` forces a FULL review (bypass the incremental marker / reset to
  head), then reconciles stale threads via D-13 engine-silence resolve, then
  re-runs the gate. This is the deliberate escape hatch: one maintainer command
  clears accumulated false-positive threads and produces a clean verdict, instead
  of the 8 manual GraphQL resolves PR #16 required.

### Claude's Discretion
- Exact suppress-list storage format/location for D-14/15 (fenced block in the
  sticky vs a base-ref `.github/` file) — research to pick, honoring base-ref-only
  + PR-scope + the compact per-entry record.
- Exact `/prevue` command parser/grammar and the `author_association` set edge
  cases (e.g. whether CONTRIBUTOR is ever allowed) for D-16.
- "Region snapshot" representation for D-15 auto-expire (reuse the D-09
  region-overlap heuristic).
- Exact `normalize(title)` rule and the fingerprint hash function (D-04).
- Known-issues list cap value N and whether it is a `prevue.yml` knob (D-07).
- Whether incremental review is opt-out via config vs always-on (default
  always-on; a knob like `review.incremental: true` is acceptable — match the P6
  `extra="forbid"` section style).
- Exact marker SHA format / regex and where the parse/write helper lives (D-01).
- "Line region changed" detection precision (hunk-overlap heuristic) for D-09.
- The classify↔incremental-scope sequencing in `run_review` (mirror the P7
  packed-set sequencing principle: paid LLM fallback only touches in-scope files).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` §"Phase 8: Incremental & Stateful Review Lifecycle" —
  goal statement, LIFE-01/02/04 mapping.
- `.planning/REQUIREMENTS.md` — **LIFE-01** (incremental since last-reviewed SHA;
  the 2026-06-14 note scoping BOTH classify + review and ruling cross-file
  call-graph out of scope), **LIFE-02** (existing PR comments as engine context +
  deterministic fingerprint backstop), **LIFE-04** (auto-resolve outdated inline
  threads); the **Out of Scope** rows ("Full codebase graph/indexing" =
  no persistent state) that bound this phase; **LIFE-03** stays v2.
- `.planning/phases/07-customization-hardening/07-CONTEXT.md` §Deferred Ideas —
  this exact phase was pre-scoped there (incremental/lifecycle review, the
  persistent-cross-run-state observation); §decisions D-23 (partial → never green
  PASS) which D-11 extends to carried findings.
- `.planning/phases/06-reusable-workflow-hybrid-classification/06-CONTEXT.md` —
  consumer checkout at `base.sha`, batched `classify()` fallback, the neutral
  skip path (`conclude_skip_check` / `upsert_skip_note`) and `.github/prevue.yml`
  config precedence (for any new incremental knob).

### Added scope (LIFE-03 + LIFE-05) — read before planning the gap closure
- `.planning/REQUIREMENTS.md` — **LIFE-05** (smarter inline thread lifecycle; the
  2026-06-16 note enumerating the PR #16 dogfood gaps: fixing code does not
  dismiss stale threads; resolve gated on delta+region+engine-silent; v2→phase-8)
  and **LIFE-03** (manual `/review` trigger; separate `issue_comment` surface +
  required base-context/write-gating security review).
- `.github/workflows/prevue-review.yml` — the existing `pull_request` trigger and
  permissions block; LIFE-03 adds an `issue_comment` trigger path (D-16) that
  must auth before checkout. `.github/prevue.yml` — `min_severity_to_fail:
  warning` (the dogfood setting that made the treadmill fail the gate).
- PR #16 (`https://github.com/Doki064/prevue/pull/16`) review history — the
  concrete failure: engine re-emits false positives every run; `graphql.py`
  queried the non-existent `side` field on `PullRequestReviewThread` (should be
  `diffSide`) so `fetch_review_threads` failed silently on every run, disabling
  all resolution. Already fixed in code; LIFE-05 builds on the now-working fetch.

### Code to wire / extend
- `src/prevue/github/comments.py` — `MARKER` (add `head=<sha>`), `_upsert_marker_comment`,
  `render_body` Metadata, `post_inline_review` (stale-cleanup scoping D-05,
  refresh-on-escalation D-06), `_existing_prevue_inline_by_location` /
  `inline_location_key` (fingerprint re-derivation source), `render_inline_comment`
  + `SEVERITY_BADGES` (severity parse-back contract D-12). New: fingerprint helper,
  GraphQL thread-resolve helper (D-08/10).
- `src/prevue/github/diff.py` — `fetch_diff()` (whole base..head today); add the
  incremental compare-API path + ancestor check (D-02/03).
- `src/prevue/github/client.py` — `PrContext`, `get_authenticated_pull`,
  `get_repo`; add compare/commits access and the GraphQL call surface (D-03/10).
- `src/prevue/review.py` — `run_review` orchestration; insert read-marker →
  incremental-scope → carry-forward → known-issues-list → gate-over-open-set
  wiring (D-01/02/05/07/11).
- `src/prevue/gate.py` — `apply_gate` / `GateResult`; extend input to the union
  of new + carried-unresolved findings (D-11).
- `src/prevue/engines/prompt.py` — `build_prompt`, `UNTRUSTED DATA` fencing;
  inject the fenced known-issues list (D-07).
- `src/prevue/models.py` — `Finding`, `DiffBundle` (carries `base_sha`/`head_sha`);
  any fingerprint field if findings need to carry it.
- `src/prevue/github/positions.py` — existing position validation; reused when
  re-placing carried/updated findings.

### Stack facts
- `.planning/research/STACK.md` — PyGithub 2.9.x capabilities/limits (note:
  GitHub **REST** for compare; **GraphQL** required for `resolveReviewThread`),
  permissions/secrets boundary, pins.
- `.planning/research/PITFALLS.md` / `.planning/research/ARCHITECTURE.md` —
  cross-run-state and idempotency hazards relevant to incremental upsert.
- `CLAUDE.md` §Technology Stack / §What NOT to Use — PyGithub batched-review
  pattern, no `secrets: inherit`, minimal token scopes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `post_inline_review` (`comments.py:388`) already upserts inline comments by
  `(path,line,side)` and reconciles a stale set — the carry-forward change (D-05)
  is a scoping tweak to its stale set, plus swapping delete→resolve for the
  outdated case (D-08), not a rewrite.
- `_existing_prevue_inline_by_location` + `_is_prevue_inline_comment`
  (`comments.py:347-370`) already enumerate trusted Prevue inline comments — the
  source for re-deriving fingerprints and severities from live comments (D-01/12).
- `SEVERITY_BADGES` + `render_inline_comment` (`comments.py:20,73`) define the
  badge↔severity mapping; D-12 just needs the documented inverse.
- `conclude_skip_check` / `upsert_skip_note` (P6) — reuse for the rebase
  full-review reset path messaging if needed.
- `apply_gate` / `GateResult.partial` (`gate.py`) — the verdict ladder that D-11
  extends to carried findings (already has the partial→neutral precedent, D-23).
- `DiffBundle` already carries `base_sha` and `head_sha` (`diff.py:23-28`) — the
  incremental compare just adds a "since" SHA.

### Established Patterns
- **State lives in PR comments, deterministic Python owns writes** (P1) — D-01
  marker SHA + re-derive-from-comments is the canonical extension of this.
- **Fail-safe verdicts: never false-green** (P4/P7 D-23) — D-11 carried-findings
  gate follows it.
- **Untrusted-data fencing in `prompt.py`** (P4/P7 SECR-02) — the known-issues
  list (D-07) reuses it; the list is engine-derived text, treat as untrusted.
- **Minimal token scopes, documented** (WKFL-04) — the GraphQL resolve call
  (D-10) must stay within `pull-requests: write`; verify in research.

### Integration Points
- `review.py:run_review` — the orchestration seam: read marker SHA → decide
  full vs incremental → fetch scoped diff → carry-forward reconciliation →
  known-issues list into prompt → gate over open set → resolve outdated threads →
  write marker with new head SHA.
- `diff.py:fetch_diff` — incremental compare-API + ancestor check land here.
- `comments.py` — marker SHA read/write, stale-cleanup scoping, GraphQL resolve,
  severity parse-back.
- `gate.py:apply_gate` — open-set verdict input.

</code_context>

<specifics>
## Specific Ideas

- **Stateless by construction** — the user steered every storage choice toward
  "re-derive from the live PR comments" over persisting a parallel state block,
  to avoid drift (someone deletes a comment; stored state lies). SHA-only marker.
- **Within-file context worry** — the user explicitly flagged that an incremental
  change can relate to earlier work (a function call, class inheritance). Resolved
  by: cross-file = out of scope (documented); within-file = send the full current
  file patch for in-scope files (D-02), not just the micro-hunk.
- **Severity must not silently regress to green** — the user chose to discuss the
  verdict question specifically; D-11 (gate over all open findings) is the direct
  answer, extending the P7 "false green is the worst outcome" stance.
- **Quiet by default** — keep matched comments as-is (no churn) unless severity
  escalates (D-06); resolve rather than delete to preserve history (D-08).

</specifics>

<deferred>
## Deferred Ideas

- **LIFE-03 — manual `/prevue` comment trigger** — ✅ promoted INTO this phase
  on 2026-06-16 (D-16/D-17). No longer deferred. Its base-context-execution
  security review is now an in-phase requirement, not a v2 blocker.
- **Cross-file call-graph / semantic impact analysis** — out of scope for this
  phase and v1 (needs full repo indexing; contradicts the stateless/token thesis).
  Documented, not lost.
- **Sticky Findings index vs live inline on rephrase-at-same-line (UAT #23, 2026-06-15)** —
  Discuss chose D-06 for **same-fingerprint** matches only (keep inline unless
  severity escalates; ignore cosmetic body/title changes). It did **not** decide
  the case where the engine re-reports the **same `(path, line)` with a different
  normalized title** (new fingerprint). Implementation today splits behavior:
  `post_inline_review` skips edit by **location** (quiet, old inline title stays);
  `_open_set_findings` drops the carried prior when current emits any finding at
  that location, so `render_findings_table(gate.placed)` shows the **new engine
  title** while the diff still displays the **old** inline thread — violating the
  LIFE-02 spirit ("never drop still-valid comments") for the sticky overview and
  the D-11 "all open findings" narrative for humans (gate counts may still fail).
  Codified by `test_open_set_dedupes_carried_prior_at_same_line_as_current` but
  not an explicit discuss choice. **Fix candidate (post-phase):** build sticky
  Findings rows from `derive_prior_findings` (live open comments) merged with
  current-run findings, or keep carried in open-set when inline was not updated;
  align inline skip-edit with D-06 fingerprint match rather than bare location.
  **Status 2026-06-16:** partially addressed during PR #16 — `_open_set_findings`
  now keeps the most-severe current finding per location and treats unparseable
  prior severity conservatively; D-13 full-review-authoritative resolve further
  reduces drift. Remaining sticky-vs-inline title alignment still open; fold into
  the LIFE-05 plan if cheap.

</deferred>

---

*Phase: 8-Incremental & Stateful Review Lifecycle*
*Context gathered: 2026-06-15 · LIFE-03 + LIFE-05 gap closure added: 2026-06-16*
