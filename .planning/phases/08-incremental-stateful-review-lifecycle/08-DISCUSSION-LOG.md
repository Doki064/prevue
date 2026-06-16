# Phase 8: Incremental & Stateful Review Lifecycle - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 8-incremental-stateful-review-lifecycle
**Areas discussed:** LIFE-01 incremental scope + rebase, LIFE-02 finding identity / dedupe, LIFE-02 engine-context vs deterministic, LIFE-04 outdated threads, gate verdict on incremental runs

User selected **all** offered gray areas, then opted to also decide the incremental-run verdict question surfaced mid-discussion.

---

## LIFE-01 — Incremental scope + rebase

### Last-reviewed SHA storage

| Option | Description | Selected |
|--------|-------------|----------|
| SHA in marker `<!-- prevue:sticky head=<sha> -->` | Single source, upsert anchor, one regex | ✓ |
| Hidden data block | SHA + fingerprints + thread IDs JSON; room to grow but drift risk | |
| Visible Metadata line | Human-readable, parse user-visible text (fragile) | |

**User's choice:** SHA in marker (after asking what fingerprints are / how the data block grows).
**Notes:** User was initially unsure A vs B. Explained fingerprints (stable finding identity, line-excluded) and that the data block could persist fingerprints + thread IDs but the live PR comments are the real ground truth (stored state drifts). User then chose SHA-only marker + re-derive fingerprints from live comments.

### Per-file diff granularity for in-scope files

| Option | Description | Selected |
|--------|-------------|----------|
| Full current base..head patch per in-scope file | File set incremental; within-file context preserved | ✓ |
| Only lastSHA..head hunks | Strictly minimal; risks losing within-file context | |
| Hunks + surrounding context | Middle ground; fuzzy bounds | |

**User's choice:** Full current patch per in-scope file.
**Notes:** User wanted incremental ("A") but worried changes may relate to a previous commit (function call, class inheritance). Clarified: cross-file call-graph impact is explicitly OUT of scope (LIFE-01 note); within-file context is preserved by sending the full current file patch for in-scope files. The dominant token win is skipping untouched *files*, not shrinking each file's patch.

### Force-push / rebase / squash

| Option | Description | Selected |
|--------|-------------|----------|
| Detect non-ancestor → full re-review | Compare API status / merge-base; reset marker | ✓ |
| Full re-review only if compare errors | Simpler; diverged-but-valid compare could mislead | |
| Always best-effort incremental | Cheapest; can review a confusing range | |

**User's choice:** Detect non-ancestor → full re-review (recommended).

---

## LIFE-02 — Finding identity / dedupe & carry-forward

### Fingerprint definition

| Option | Description | Selected |
|--------|-------------|----------|
| Content-based, line-excluded | `path + normalized title (+ severity)`; survives line shifts | ✓ (refined) |
| Content + coarse line band | Adds ±N line bucket tiebreak | |
| Anchor-based path+line+side | Current inline key; breaks on line shift | |

**User's choice:** Content-based, line-excluded → **refined** to `path + normalized-title` only (severity dropped from identity).
**Notes:** Follow-up: user asked "is there any case the new finding is better than existing?" Surfaced two cases — mis-positioned existing comment (routed to LIFE-04) and refreshed body/escalated severity. To handle severity cleanly, dropped severity from the identity (so a re-rating is the same finding, not a new one) and made severity a refreshable attribute.

### Severity-in-identity refinement

| Option | Description | Selected |
|--------|-------------|----------|
| Drop severity from identity | Same issue re-rated keeps one fingerprint | ✓ |
| Keep severity in identity | Severity change creates a new finding + orphan | |

**User's choice:** Drop severity from identity.

### On a same-fingerprint match

| Option | Description | Selected |
|--------|-------------|----------|
| Refresh only on severity escalation | Keep as-is; edit in place only when severity worsens | ✓ |
| Always keep existing as-is | Quietest; worsened issue won't update | |
| Always refresh in place | Always current; edit churn every push | |

**User's choice:** Refresh only on severity escalation.

### Carry-forward (prior comments on un-retouched files)

| Option | Description | Selected |
|--------|-------------|----------|
| Scope stale-cleanup to in-scope files | Out-of-scope comments untouched; no churn | ✓ |
| Re-derive + re-post all prior findings | Explicit but heavy; re-post churn | |

**User's choice:** Scope stale-cleanup to in-scope files only.

---

## LIFE-02 — Engine-context vs deterministic dedupe

### Dedupe mix

| Option | Description | Selected |
|--------|-------------|----------|
| Compact known-issues list | Short path+title+line list, "do not repeat" + fingerprint backstop | ✓ |
| Deterministic only | Zero added prompt tokens; engine re-derives anyway | |
| Full prior comment bodies | Max awareness; high token cost, scales badly | |

**User's choice:** Compact known-issues list (recommended).

### Bounding the list

| Option | Description | Selected |
|--------|-------------|----------|
| Cap to in-scope files + count limit | Naturally small; backstop covers the rest | ✓ |
| Global count cap only | Can spend tokens on out-of-scope findings | |
| No cap | Unbounded prompt growth | |

**User's choice:** Cap to in-scope files + count limit.

---

## LIFE-04 — Outdated threads: resolve vs delete

### Stale handling change

| Option | Description | Selected |
|--------|-------------|----------|
| Resolve outdated; delete only own dups | GraphQL resolveReviewThread; preserves history | ✓ |
| Resolve everything, never delete | Leaves own dups as resolved clutter | |
| Keep delete (no resolve) | Contradicts LIFE-04 | |

**User's choice:** Resolve outdated; delete only own same-run dups.

### Resolution trigger

| Option | Description | Selected |
|--------|-------------|----------|
| In-scope file + line changed + not re-reported | Conservative; untouched-file findings safe | ✓ |
| GitHub native 'outdated' flag | Simple; risks resolving still-valid findings | |
| Any prior finding not re-emitted | Aggressive; wrongly resolves out-of-scope findings | |

**User's choice:** In-scope file + line changed + not re-reported.

### GraphQL handling

| Option | Description | Selected |
|--------|-------------|----------|
| Thin GraphQL call via same token | requests + GITHUB_TOKEN; verify scope in research | ✓ |
| Flag as research spike first | De-risk auth/scope + thread-ID mapping before planning | |

**User's choice:** Thin GraphQL call via same token (verify scope in research).

---

## Gate verdict on incremental runs

### Finding set the gate evaluates

| Option | Description | Selected |
|--------|-------------|----------|
| All currently-open findings | new ∪ carried-unresolved − resolved; no false green | ✓ |
| This run's findings only | Current behavior; clean push false-greens over open error | |

**User's choice:** All currently-open findings (recommended).

### Carried-forward severity source

| Option | Description | Selected |
|--------|-------------|----------|
| Parse from existing comment body badge | No storage; inverse of SEVERITY_BADGES | ✓ |
| Store severity in marker block | Contradicts SHA-only marker; drift risk | |
| Fixed severity floor | Over-blocks (carried info note would fail) | |

**User's choice:** Parse from existing comment body (recommended).

---

## Claude's Discretion

- Exact `normalize(title)` rule and fingerprint hash function.
- Known-issues list cap N and whether it is a `prevue.yml` knob.
- Incremental opt-out config knob vs always-on (default always-on).
- Exact marker SHA format / regex and helper location.
- "Line region changed" detection precision (hunk-overlap heuristic).
- classify ↔ incremental-scope sequencing in `run_review`.

## Deferred Ideas

- **LIFE-03** manual `/review` comment trigger — stays v2 (separate trigger surface + security review).
- **Cross-file call-graph / semantic impact** — out of scope for v1 (needs full repo index; contradicts stateless/token thesis).

---

# Addendum — 2026-06-16: LIFE-03 + LIFE-05 gap closure

**Scope:** LIFE-03 + LIFE-05 only (LIFE-01/02/04 above NOT re-discussed).
**Motivation:** PR #16 dogfood exposed a false-positive carry-forward treadmill — the LLM
engine re-emits false positives every run, fixing code does not dismiss stale inline threads
(D-09 resolve gated on delta + region-change + engine-silent), and with
`min_severity_to_fail: warning` the check could only be made green by 8 rounds of manual
GraphQL thread resolution. (Root cause also found & fixed: `graphql.py` queried a
non-existent `side` field → `fetch_review_threads` failed silently every run, disabling all
resolution; corrected to `diffSide`.)

## LIFE-05 — Stale-thread auto-resolve trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Full-review authoritative | On full-scope review, resolve any prior thread the engine did not re-report; drop region-change gate for full runs only | ✓ |
| Keep region-change gate | Status quo even on full reviews | |
| Engine-silence for both scopes | Most aggressive; risks resolving still-valid findings on partially-read files | |

**User's choice:** Full-review authoritative → **D-13**.

## LIFE-05 — False-positive handling (dismiss vs fixed)

| Option | Description | Selected |
|--------|-------------|----------|
| Resolve = dismiss, stateless | Only clears findings the engine stops emitting; persistent FPs survive | |
| Fingerprint suppress-list | Kills persistent FPs but adds state + drift + security surface | |
| Confidence-threshold suppression | Really QUAL-01 v2 | |
| **Hybrid: stateless default + audited `/prevue dismiss`** | Bounds state/security cost to a maintainer-gated command | ✓ |

**User's choice:** Hybrid → **D-14**, with the explicit requirement that the mechanism must
**ensure dismissed findings are really false positives, not real findings being re-emitted.**
**Notes:** User requested up/down sides of stateless (A) vs suppress-list (B) before deciding.

## LIFE-05 — Dismiss safety guards

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-expire on region change | Invalidate dismissal when code at the location changes | ✓ |
| PR-scoped, never repo-wide | Base-ref storage, this PR only | ✓ |
| Severity gate + audit | Live finding only; actor/time/reason; errors need explicit confirm | ✓ |
| Re-report on escalation | Higher-severity re-emission overrides dismissal | ✓ |

**User's choice:** All four → **D-15**.
**Notes:** User requested up/down sides of each + recommended combination. Roles: #3 creation
gate, #1/#4 invalidation triggers, #2 storage scope.

## LIFE-03 — Manual trigger surface & security

| Option | Description | Selected |
|--------|-------------|----------|
| `/prevue review`, write-assoc gated | author_association in {OWNER,MEMBER,COLLABORATOR}; auth before PR-head checkout; base context | ✓ |
| Bare `/review` command | Collides with other bots/UI | |
| Scaffold only, defer security | Less safe to ship | |

**User's choice:** `/prevue review`, write-assoc gated → **D-16**.

## LIFE-03 — Manual trigger behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Full re-review + reconcile + re-gate | Bypass incremental marker, reconcile via D-13, re-run gate | ✓ |
| Incremental refresh only | Won't clear stale threads | |
| Full re-review, no thread cleanup | Stale threads persist | |

**User's choice:** Full re-review + reconcile + re-gate → **D-17**.

## Claude's Discretion (addendum)

- Suppress-list storage format/location (sticky fenced block vs base-ref `.github/` file).
- `/prevue` command grammar + `author_association` edge cases.
- "Region snapshot" representation reusing the D-09 overlap heuristic.

## Deferred Ideas (addendum)

- **Confidence/impact scoring (QUAL-01)** — remains v2; LIFE-05 dismiss is human-gated, not score-driven.
- **Repo-wide / cross-PR suppression** — explicitly out; belongs in skill/prompt tuning.
- **Sticky-vs-inline title alignment on rephrase-at-same-line** — partially addressed during PR #16; fold into LIFE-05 plan if cheap.
