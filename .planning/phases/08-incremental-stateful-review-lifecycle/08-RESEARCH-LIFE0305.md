# Phase 8 (Added Scope): LIFE-03 + LIFE-05 Gap Closure — Research

**Researched:** 2026-06-16
**Domain:** Manual `/prevue` comment-command trigger over `issue_comment` (authorization-before-execution), full-review-authoritative thread auto-resolve, and an audited PR-scoped dismiss suppress-list — built ON the shipped Phase 8 incremental/stateful machinery (08-01..08-10).
**Confidence:** HIGH (codebase-verified against the shipped fingerprint/GraphQL/region/scope code) / MEDIUM-HIGH on the `issue_comment` security pattern (official GitHub docs + GitHub Security Lab, with one load-bearing correction to the locked authorization signal).

> **This is additive research.** It does NOT re-derive the shipped LIFE-01/02/04 design (see `08-RESEARCH.md`). It treats the following as a stable, verified foundation to extend:
> - `fingerprint(path, title)` / `normalize_title` (`src/prevue/fingerprint.py`) — content-addressed identity, sha256[:16].
> - `finding_region_changed` / `regions_changed` / `regions_from_comparison` (`positions.py`, `diff.py`) — the D-09 hunk-overlap heuristic (context window C=3).
> - GraphQL `fetch_review_threads` (with the landed `diffSide` fix) + `resolve_review_thread` (best-effort, never raises) (`github/graphql.py`).
> - `decide_scope` → `("full"|"incremental"|"noop", in_scope_paths, comparison)` (`diff.py`).
> - `derive_prior_findings` / `_derive_prior_findings_with_threads` / `PriorFinding` / `parse_severity_from_body` (`comments.py`).
> - `_open_set_findings` open-set union, `apply_gate` over the open set (D-11) (`review.py`, `gate.py`).
> - Marker `<!-- prevue:sticky head=<sha> -->` parse/render (`comments.py`).

---

<user_constraints>
## User Constraints (from CONTEXT.md — Added scope 2026-06-16)

### Locked Decisions (research implementation for these; no alternatives)

- **D-13 — Full-review-authoritative auto-resolve.** On a FULL-scope review, RESOLVE any prior Prevue thread whose fingerprint the engine did NOT re-report this run (engine silence over a fully re-read file = finding gone). Drops D-09's region-change requirement **for full runs only**; incremental runs keep the conservative D-09 gate.
- **D-14 — Hybrid dismiss model.** Explicit, audited `/prevue dismiss <fingerprint|thread>` writes a bounded suppress-list for persistent false positives the engine re-emits every run. Default stateless `resolve = dismiss` stays for engine-silent findings.
- **D-15 — Dismiss safety, four guards.** (1) Creation gate: only dismiss a finding that EXISTS this run, by a write-assoc maintainer, recording actor+timestamp+reason; 🔴 error needs explicit confirmation; surface in sticky. (2) Auto-expire on region change: store a line-region snapshot; if code at location changes per the D-09 `finding_region_changed` heuristic, the dismissal invalidates → finding re-surfaces. (3) Re-report on escalation: engine re-emits at HIGHER severity → dismissal overridden. (4) PR-scoped, base-ref-only storage: suppress-list lives in the PR base-ref surface, NEVER read from PR head, applies only to this PR. Per-entry: `{fingerprint, region-snapshot, severity, actor, timestamp, reason}`.
- **D-16 — `/prevue` command surface via `issue_comment`, write-assoc gated.** Commands `/prevue review`, `/prevue dismiss <id>`, `/prevue resolve <id>`. Authorize on author write access. **Authorization check runs BEFORE any PR-head checkout or code execution**; job runs in base context with minimal scopes; comment body is untrusted. Own security review of base-context execution + write-gating REQUIRED before ship.
- **D-17 — Trigger behavior.** `/prevue review` forces a FULL review (bypass incremental marker / reset to head), reconciles stale threads via D-13 engine-silence resolve, then re-runs the gate.

### Claude's Discretion (resolved below with a single recommendation each)
1. Suppress-list storage format/location (sticky fenced block vs base-ref `.github/` file).
2. `/prevue` parser grammar + `author_association` set edge cases (is CONTRIBUTOR allowed?).
3. "Region snapshot" representation for D-15 auto-expire.

### Out of Scope (ignore completely)
- Confidence/impact scoring (QUAL-01, v2). Cross-PR / repo-wide suppression. Cross-file call-graph. Re-research of the shipped incremental marker/compare/carry-forward machinery (extend, don't rebuild).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LIFE-03 | Manual `/prevue review`/`dismiss`/`resolve` via `issue_comment`, write-assoc gated, base-context execution, untrusted comment body | §"VERIFIED-safe `issue_comment` security pattern", §"D-16 implementation", §"Discretion 2: parser + authorization" |
| LIFE-05 | Full-review-authoritative auto-resolve + hybrid audited dismiss for persistent false positives | §"D-13 implementation", §"D-14/D-15 implementation", §"Discretion 1: storage", §"Discretion 3: region snapshot" |
</phase_requirements>

---

## Summary

The shipped Phase 8 code is **further along than `08-RESEARCH.md` describes**: `fingerprint`, GraphQL `fetch_review_threads`/`resolve_review_thread`, severity parse-back, region-overlap, and the open-set gate are all live and tested. The gap-closure work is therefore mostly **wiring three new behaviors into well-defined existing seams**, not new subsystems:

1. **D-13 (machine half of the treadmill break)** is a small predicate change inside the *existing* resolve path: on a FULL run, resolve every prior whose fingerprint is absent from current findings, *dropping* the `finding_region_changed` gate that `resolve_outdated_prior_findings` currently enforces unconditionally. The function already takes `in_scope_paths`, `regions_by_path`, `current_fingerprints`, and a fetched `threads` list — D-13 adds a `full_run: bool` (or "authoritative") flag that skips the region check.

2. **D-16/D-17 (human half)** is the genuinely new surface: an `issue_comment`-triggered entry point that parses `/prevue …`, authorizes the commenter, resolves the comment's PR, and dispatches to `review` (force-full + reconcile + re-gate), `resolve`, or `dismiss`. **The single highest-risk surface in the project.** The locked decision says "authorize on `author_association ∈ {OWNER, MEMBER, COLLABORATOR}`" — research finds that `author_association` is **NOT a reliable proxy for write access** (a read-only outside collaborator returns `COLLABORATOR`; a write-privileged org member can return `CONTRIBUTOR`). The safe, official mechanism is the **collaborator-permission API** (`GET /repos/{owner}/{repo}/collaborators/{username}/permission` → `none|read|write|admin`), available as `Repository.get_collaborator_permission(login)` in the installed PyGithub 2.9.1 `[VERIFIED]`. **Recommendation: use `author_association` as a cheap first filter but make the authoritative gate `permission ∈ {write, admin}`.** This is a strengthening of D-16's intent (write-access gating), not a contradiction of it.

3. **D-14/D-15 (dismiss)** introduces the project's one sanctioned persistent record. **Recommended storage: a fenced, machine-readable block inside the existing sticky comment** (re-derive-from-comments, no new file, no extra checkout, automatically PR-scoped) — see Discretion 1. Each dismiss carries `{fingerprint, region_snapshot, severity, actor, timestamp, reason}` and is enforced at gate-assembly time with the three invalidation guards.

**Primary recommendation:** Land D-13 first (smallest, pure predicate change, immediately reduces PR #16 pain). Land the dismiss store + guards (D-14/D-15) second as pure functions over the open set. Land the `issue_comment` trigger (D-16/D-17) last, behind a mandatory pre-ship threat-model + a `checkpoint:human-verify` on a live sandbox PR — and **replace the `author_association`-only gate with the collaborator-permission check**.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Full-run engine-silence resolve (D-13) | `comments.py` `resolve_outdated_prior_findings` (predicate) | `review.py` (passes `scope`/full flag) | Resolve logic already lives here; D-13 is a gate-condition relaxation for full runs |
| `/prevue` command parse (D-16) | NEW `src/prevue/commands.py` (pure parser) | — | Deterministic, untrusted-input parser — ideal isolated TDD unit |
| Commenter authorization (D-16) | GitHub REST collaborator-permission API | NEW `commands.py` / `client.py` helper | Write-access is a server-side fact; `author_association` is unreliable (see Pitfall 1) |
| `issue_comment` → PR resolution (D-16) | GitHub REST (`get_pull(number)`) | NEW event-context loader | `issue_comment` payload has no PR head SHA; must fetch the PR |
| Force-full + reconcile + re-gate (D-17) | `review.py` `run_review` (new entry/flag) | `decide_scope` bypass | Reuses the full-review path; just forces scope=full and ignores the marker |
| Dismiss suppress-list storage (D-14) | Sticky comment fenced block (the datastore) | `comments.py` (parse/write) | Honors base-ref-only + PR-scope + re-derive-from-comments (P1); no new persistence tier |
| Dismiss enforcement + 3 guards (D-15) | `review.py` open-set assembly | `fingerprint`/`finding_region_changed` (reuse) | Suppression is a filter over the open set; guards reuse shipped predicates |
| Dismiss audit surfacing (D-15) | `comments.py` `render_body` (sticky section) | — | Audit must be visible; sticky already the human-facing surface |

---

## Standard Stack

**No new third-party dependencies.** Everything is shipped/pinned and verified installed.

| Library | Version | Purpose | Provenance |
|---------|---------|---------|-----------|
| PyGithub | 2.9.1 (installed) | `Repository.get_collaborator_permission(login)` for D-16 write-gate; `repo.get_pull(number)` to resolve the `issue_comment`→PR head SHA; existing compare/GraphQL | `[VERIFIED: uv run hasattr check — get_collaborator_permission=True, get_pull=True]` |
| requests | (installed, used by `graphql.py`) | reused GraphQL transport for `resolve` command path | `[VERIFIED: github/graphql.py imports requests]` |
| pydantic | 2.13.x | typed `DismissEntry` model + any new `ReviewConfig`/command-config knob (`extra="forbid"`) | `[VERIFIED: gate.py ReviewConfig, config.py extra="forbid" style]` |
| hashlib / re (stdlib) | — | reuse `fingerprint` for dismiss identity; parser regex | `[VERIFIED: fingerprint.py]` |

**Installation:** None — no new packages. **Package Legitimacy Audit: N/A — zero new installs.**

**Version verification:**
```bash
uv run python -c "from github.Repository import Repository; print(hasattr(Repository,'get_collaborator_permission'))"  # True (confirmed this session)
```

---

## VERIFIED-safe `issue_comment` security pattern (feeds the mandatory threat model)

> This section is the authoritative input to the planner's `<threat_model>` block and the required pre-ship security review for D-16. CLAUDE.md flags `pull_request_target` + untrusted-fork-code execution as the #1 Actions foot-gun; the `issue_comment` trigger is structurally adjacent and must be treated with the same rigor.

### Fact 1 — `issue_comment` runs from the **default branch**, in **base-repo context**, with a **read/write `GITHUB_TOKEN`**
The `issue_comment` event is a *repository* event, not a PR event. `GITHUB_REF` = the default branch; `GITHUB_SHA` = the last commit on the default branch. The workflow definition and any scripts it runs come from **trusted base-repo code**, NOT from the PR head. `[CITED: docs.github.com/en/actions/.../events-that-trigger-workflows — issue_comment: "Default branch" ref, "Last commit on default branch" SHA]`

**Consequence (the safety property D-16 relies on):** an `issue_comment`-triggered job that **never checks out the PR head** executes only trusted base code, even when the commenter is hostile. The comment *body* is the only attacker-controlled input, and it is data, not code, as long as it is never interpolated into a shell template (Fact 4). Unlike `pull_request_target`, no fork code runs — provided we do not add a PR-head checkout step. Prevue already does diff analysis **via the API with no checkout** (`fetch_diff` uses `pr.get_files()`); the `/prevue review` path can do the same, preserving the no-checkout invariant.

### Fact 2 — `issue_comment` fires for BOTH issues and PRs; gate on `issue.pull_request`
The same event fires on plain-issue comments. Distinguish a PR comment via `github.event.issue.pull_request` (a truthy object only when the issue is a PR). `[CITED: docs.github.com/.../events-that-trigger-workflows — "use the github.event.issue.pull_request property in a conditional"]`. Gate the whole job: `if: github.event.issue.pull_request && startsWith(github.event.comment.body, '/prevue')`.

### Fact 3 — the payload has **no PR head SHA**; fetch the PR separately
The `issue_comment` payload carries the comment, the issue (`number`, `author_association`), and `repository` — but **not** the PR head SHA / base SHA / head-repo. You must call `repo.get_pull(issue.number)` to obtain `pr.head.sha`, `pr.base.sha`, and `pr.head.repo.full_name` (the fork guard). `[VERIFIED: client.py load_pr_context reads event["pull_request"] which does NOT exist on issue_comment events — a new loader is REQUIRED; see landmine §L1]`. The same `get_pull` call provides the fork guard for SECR-01.

### Fact 4 — comment body is untrusted: never interpolate into shell; pass via env, parse in Python
Per GitHub Security Lab: `${{ github.event.comment.body }}` interpolated into a `run:` step is a shell-injection vector (the runner builds a temp script by substitution before execution). **Mitigation: bind to an intermediate env var and read it in Python.** `[CITED: securitylab.github.com/resources/github-actions-untrusted-input — "set the untrusted input value … to an intermediate environment variable"]`
```yaml
- name: Prevue command
  env:
    PREVUE_COMMENT_BODY: ${{ github.event.comment.body }}   # data, not code
    PREVUE_COMMENT_AUTHOR: ${{ github.event.comment.user.login }}
    PREVUE_ISSUE_NUMBER: ${{ github.event.issue.number }}
    GITHUB_TOKEN: ${{ github.token }}
  run: uv run prevue command   # Python reads os.environ, parses, authorizes, dispatches
```
The Python parser must treat the body as a single untrusted string: match a strict grammar (Discretion 2), never `eval`/`shell=True`, never pass the raw `<id>` token into a subprocess argv without validation (fingerprints are `[0-9a-f]{16}`; thread IDs are GitHub node IDs `[A-Za-z0-9_=-]+`). This mirrors the existing SECR-02 fencing posture.

### Fact 5 — authorize on **write access**, not `author_association` alone (the load-bearing correction)
`author_association` is the locked signal in D-16, but research shows it is **not a reliable write-access proxy**:
- A read-only **outside collaborator** returns `COLLABORATOR` regardless of permission level. `[CITED: michaelheap.com/github-actions-check-permission; community discussion #643]`
- A write-privileged org member can surface as `CONTRIBUTOR` (GitHub returns the "most recent"/inconsistent association). `[CITED: actions/github-script#643, community #18690]`

The official reliable check is the collaborator-permission endpoint:
```
GET /repos/{owner}/{repo}/collaborators/{username}/permission  →  {"permission": "none"|"read"|"write"|"admin", ...}
```
Available as `Repository.get_collaborator_permission(login) -> str` in PyGithub 2.9.1 `[VERIFIED]`.

**Recommended authorization (strengthens D-16, honors its write-access intent):**
1. Cheap pre-filter in workflow `if:` — `author_association` ∈ {OWNER, MEMBER, COLLABORATOR} (drops obvious NONE/FIRST_TIMER spam without spending an API call).
2. **Authoritative gate in Python BEFORE any dispatch:** `repo.get_collaborator_permission(author) in {"write", "admin"}`. If not satisfied → post a terse "not authorized" reaction/comment and exit 0 (no review, no resolve, no dismiss).
3. Run the authorization gate as the **first** Python action, before resolving the PR diff or invoking the engine — "auth before execution" per D-16.

> **CONTRIBUTOR edge case (Discretion 2):** Do NOT authorize on `CONTRIBUTOR` via `author_association` — it means "has committed before", not "has write access", and a one-time external contributor to a public repo legitimately carries it. Authorize CONTRIBUTOR-tagged users only if the permission API independently returns `write`/`admin`. This is exactly why the permission API is the authoritative gate.

### Fact 6 — minimal scopes unchanged; declare them on the new trigger
The new `issue_comment` workflow keeps the existing least-privilege block: `contents: read, pull-requests: write, checks: write`. `dismiss`/`resolve` need only `pull-requests: write` (comment edit + GraphQL resolve). `review` needs `contents: read` (compare/diff API) + `checks: write`. **No `contents: write`, no `pull_request_target`, no `secrets: inherit`** — consistent with REQUIREMENTS Out-of-Scope and CLAUDE.md "What NOT to Use".

### Threat table for the planner's `<threat_model>`

| Threat | STRIDE | Mitigation (verified) |
|--------|--------|-----------------------|
| Unauthorized user triggers a privileged review/dismiss/resolve | Elevation of Privilege | Collaborator-permission gate `{write,admin}` BEFORE dispatch (Fact 5); `author_association` only a pre-filter |
| Shell/command injection via comment body | Tampering / EoP | Body passed as env var, parsed in Python; strict grammar; no `shell=True`/`eval`; validated `<id>` tokens (Fact 4) |
| Argument injection of `<id>` into engine/GraphQL | Tampering | Validate `fingerprint=[0-9a-f]{16}`, `threadId=[A-Za-z0-9_=-]+` before use |
| Fork PR uses a command to run code in base context | EoP | No PR-head checkout on the `issue_comment` path (Fact 1); fork guard via `pr.head.repo.full_name` (SECR-01) — `dismiss`/`review` on a fork PR are refused or run diff-only with no checkout |
| Malicious PR head adds a permissive suppress-list to silence security findings | Tampering | Suppress-list read from base-ref / sticky only, NEVER from PR head (D-15 guard 4); dismiss writes go only through the authorized command path |
| Replay / spoofed marker or sticky body to fake state | Spoofing | Sticky trusted-actor check (`_is_trusted_sticky_actor`) already enforced; dismiss entries authored only by the bot after an authorized command |
| Stale dismissal masks a newly-introduced bug at the same line | Tampering | Auto-expire on region change (D-15 guard 2, `finding_region_changed`) + escalation override (guard 3) |

---

## Decision-by-decision implementation guidance

### D-13 — Full-review-authoritative auto-resolve

**Touch-point:** `comments.py::resolve_outdated_prior_findings` (lines 247–302) and its caller `review.py::run_review` (lines 678–688).

Today the function unconditionally requires `finding_region_changed(stub, regions)` (line 293) before resolving. That is correct for incremental runs (a partially-read file's silence is not authoritative) but is exactly the gate that keeps PR #16's stale threads alive on a full re-read.

**Concrete change:** add an `authoritative: bool = False` (or `full_run: bool`) parameter. When `True`, **skip the region check** — resolve any in-scope prior whose fingerprint ∉ `current_fingerprints` and whose thread is not already resolved. The other three conditions are unchanged: in-scope path, fingerprint absent from current, thread exists + not already resolved.

```python
# resolve_outdated_prior_findings(...) — D-13 relaxation
if not authoritative and not finding_region_changed(stub, regions):
    continue   # incremental: keep conservative D-09 gate (region must have changed)
# authoritative (full run): engine silence over a fully re-read file IS the trigger
```

**Caller wiring (`review.py`):** `decide_scope` already yields `scope`. On `scope == "full"` (first run, force-full via D-17, or rebase/diverged), call with `authoritative=True` and `in_scope_paths = reviewed_paths` (the full set of files actually reviewed). On `scope == "incremental"`, keep `authoritative=False` and the existing `delta_paths`/`regions_by_path`. **Critical scoping note:** on a full run, `in_scope_paths` for resolve must be the files the engine actually re-read this run (`reviewed_paths` / packed files) — a prior on a file dropped by the token budget was NOT re-read, so its silence is not authoritative. Do not pass the entire PR file set blindly; pass `reviewed_paths` so a budget-skipped file's thread is carried, not resolved.

**Open-set consistency:** `_open_set_findings` already subtracts `resolved_fingerprints`. Feeding D-13's larger `resolved_fps` set into the existing call (line 692) makes the gate and sticky reflect the cleared threads automatically — no separate change.

**Landmine:** D-13 must NOT resolve a finding the engine still emits at a different `(line)` after code shifted — that's handled because resolution keys on *fingerprint absence from current*, and `fingerprint` excludes line number (D-04). A genuinely-still-present finding re-emits the same fingerprint and is excluded from resolution. Verify with a "line shifted, same finding" fixture.

---

### D-16 — `/prevue` command surface via `issue_comment`

**New files / touch-points:**
- NEW `.github/workflows/prevue-command.yml` — `on: issue_comment: types: [created]`, the env-var-isolated body (Fact 4), the same `permissions` block, no PR-head checkout.
- NEW `src/prevue/commands.py` — pure parser (Discretion 2) + dispatcher + authorization gate.
- NEW event/context loader: `client.py::load_pr_context` reads `event["pull_request"]` (line 27) which **does not exist on `issue_comment`** (§L1). Add `load_comment_context()` that reads `event["issue"]["number"]`, `event["comment"]["body"]`, `event["comment"]["user"]["login"]`, `event["comment"]["author_association"]`, then `repo.get_pull(number)` to recover `head.sha`/`base.sha`/`head.repo.full_name`.
- `cli`/entry point: add a `prevue command` subcommand alongside `prevue review`.

**Authorization (Fact 5):** first action in `prevue command` is the write-gate. `author_association` pre-filter happens in the workflow `if:`; Python re-checks `repo.get_collaborator_permission(author) in {"write","admin"}`. Unauthorized → post a one-line "🔒 `/prevue` requires write access" reply (or a `-1` reaction) and exit 0.

**Dispatch:**
- `/prevue review` → D-17 (force-full path below).
- `/prevue dismiss <id>` → D-14/D-15 dismiss-creation (must validate the finding EXISTS this run — guard 1; see below).
- `/prevue resolve <id>` → resolve a single thread by id/fingerprint via the shipped `resolve_review_thread` (best-effort), recording nothing persistent (a resolved thread is already skipped in derivation — `comments.py:215`).

**Fork guard:** after `get_pull`, if `pr.head.repo.full_name != base repo`, refuse `dismiss` (do not let fork PRs persist suppressions) and run `review` diff-only with no checkout (SECR-01 already forbids fork review in v1 — simplest correct behavior is to refuse all commands on fork PRs in v1 and say so).

---

### D-17 — `/prevue review` = force full + reconcile + re-gate

**Touch-point:** `review.py::run_review` (the `marker_for_scope` / `decide_scope` block, lines 350–360).

Today `marker_for_scope = last_sha if (review_cfg.incremental or last_sha == head_sha) else None`. For a forced full review, pass a signal (e.g. `run_review(force_full=True)` or env `PREVUE_FORCE_FULL=1` set by the command path) that makes `decide_scope` return `("full", None, comparison-or-None)` **regardless of the marker**, and resets the marker to head on write (the full path already writes `head_sha=diff.head_sha`).

**Sequencing (reuse, don't duplicate):**
1. `decide_scope` → forced `full`.
2. Run the existing full-review pipeline (filter/pack/classify/engine) over the whole PR.
3. Reconcile via D-13: `resolve_outdated_prior_findings(..., authoritative=True, in_scope_paths=reviewed_paths)`.
4. Re-gate over the open set (existing `apply_gate(_open_set_findings(...))`).
5. Write marker=head + post check.

This is the deliberate escape hatch: one authorized comment clears accumulated false-positive threads and produces a clean verdict — replacing PR #16's 8 manual GraphQL resolves.

**Same-SHA subtlety:** the shipped preflight skips the engine CLI install on same-SHA runs. A forced `/prevue review` on an unchanged head must still install the engine and run a real full review. The command workflow is a separate YAML — give it an unconditional engine install (it is only triggered by an explicit human command, so the cost is acceptable and intended). Do NOT reuse the `pull_request` preflight noop gate on the command path.

---

### D-14 / D-15 — Hybrid dismiss model + four guards

**Storage:** see Discretion 1 — recommended fenced block in the sticky comment.

**`DismissEntry` model (pydantic, `extra="forbid"`):**
```python
class DismissEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str            # [0-9a-f]{16}, reuse fingerprint()
    region: tuple[int, int]     # (start, end) RIGHT-side line range snapshot — Discretion 3
    side: Literal["RIGHT","LEFT"] = "RIGHT"
    path: str                   # needed to re-evaluate region snapshot against this run's regions
    severity: str               # severity at dismiss time (for escalation guard)
    actor: str                  # comment author login
    timestamp: str              # ISO-8601 UTC
    reason: str                 # required; for 🔴 must be explicit/non-empty (guard 1)
```

**Guard 1 — creation gate (in `prevue command` dismiss path):**
- The `<id>` must match a finding/thread that EXISTS this run. Re-derive priors (`derive_prior_findings`) and/or current findings; reject a dismiss whose fingerprint is in neither (post "no open finding matches `<id>`").
- Author must pass the write-gate (D-16).
- Record `actor + timestamp + reason`. For a finding whose current severity is `error` (🔴), require a non-empty explicit reason (the command grammar must capture it — e.g. `/prevue dismiss <id> reason: <text>`), else refuse with "dismissing an error requires a reason".
- Surface every dismissal in the sticky audit section (D-15) — see `render_body` extension.

**Guard 2 — auto-expire on region change (at enforcement time, in `_open_set_findings` / gate assembly):** for each active dismiss entry, recompute whether its `region` snapshot still matches. Reuse `finding_region_changed`: build a stub `Finding(path, line=region midpoint or start, side)` and test against **this run's** `regions_by_path[path]`. If the region changed (overlaps a hunk touched this run), the dismissal is **invalidated** → do NOT suppress; the finding re-surfaces. This is the load-bearing "is it still a FP?" guard.

> **Region-snapshot semantics (Discretion 3):** store the `(start, end)` RIGHT-side line range that `regions_changed` produced for the finding's location at dismiss time — i.e. the same `(min,max)` tuple shape `regions_changed`/`regions_from_comparison` already emit (`positions.py:41-58`). At enforcement, the dismissal survives only while the code at that range is untouched; the moment a later push (or a forced full run) touches a hunk overlapping `[start-3, end+3]` (the C=3 window already baked into `finding_region_changed`), the dismissal expires. This reuses the exact D-09 heuristic — no new geometry.

**Guard 3 — re-report on escalation (at enforcement time):** if a current finding with the dismissed fingerprint has a strictly-higher severity than the entry's stored `severity` (use the shipped `SEVERITY_RANK`, lower rank = more severe), the dismissal is **overridden** → the finding surfaces at the new severity. Reuse the `_severity_escalated` comparison logic (`comments.py:305`).

**Guard 4 — PR-scoped, base-ref-only:** the suppress-list is read only from the sticky (authored by the trusted bot, on the base-ref-side PR conversation surface) — NEVER from any PR-head file. Storing in the sticky makes this automatic (see Discretion 1). A dismiss never crosses to another PR (a new PR has its own sticky).

**Enforcement point:** apply the surviving (non-expired, non-overridden) dismiss set as a **filter over the open set just before `apply_gate`** in `run_review`. A suppressed finding is dropped from the gate's findings (so it neither fails the gate nor posts inline) but its audit row stays in the sticky's dismiss section. Order: build open set → apply guard 2/3 to compute the *active* suppress set → subtract suppressed fingerprints → `apply_gate`.

---

## Claude's Discretion — resolved recommendations

### Discretion 1 — Suppress-list storage: **fenced block in the sticky comment** (recommended)

**Recommendation: store the dismiss suppress-list as a fenced, machine-readable block inside the existing sticky comment**, not a base-ref `.github/` file.

| Criterion | Sticky fenced block (RECOMMENDED) | Base-ref `.github/` file |
|-----------|-----------------------------------|--------------------------|
| Base-ref-only / never PR-head | ✅ Sticky is authored by the trusted bot; `_is_trusted_sticky_actor` already enforces provenance; never read from PR head | ✅ but requires the base-ref checkout to be present and trusted; the command path is no-checkout (Fact 1) — would need an extra checkout step, enlarging attack surface |
| PR-scoped | ✅ One sticky per PR — automatically scoped | ⚠️ A repo file is repo-global; PR-scoping requires per-PR file naming/keys — awkward, leak-prone |
| Re-derive-from-comments (P1) | ✅ Matches the shipped "state lives in PR comments" pattern exactly | ❌ Introduces a second state surface that can drift from the comments |
| No new persistence tier | ✅ Reuses the sticky upsert (`_upsert_marker_comment`) | ❌ Needs `contents: write` to persist, OR a PR commit — both violate minimal scopes / Out-of-Scope |
| Audit visibility (D-15) | ✅ Audit + suppress-list co-located in the human-facing sticky | ❌ A `.github/` file is invisible in the PR conversation |
| Write permission needed | `pull-requests: write` (already held) | `contents: write` (FORBIDDEN by Out-of-Scope) — disqualifying |

**The base-ref `.github/` file option is effectively disqualified** because persisting it requires `contents: write` (explicitly Out-of-Scope) or a commit to the PR, and reading it on the no-checkout command path would force a base-ref checkout. The sticky block wins on every axis.

**Concrete format** (append after the Metadata section; bounded, parseable, hidden-ish):
```markdown
### Dismissed findings
<!-- prevue:dismiss -->
```json
[
  {"fingerprint":"a1b2c3d4e5f60718","path":"src/x.py","region":[40,52],"side":"RIGHT","severity":"warning","actor":"alice","timestamp":"2026-06-16T04:30:00Z","reason":"false positive: framework injects this"}
]
```
<!-- /prevue:dismiss -->
```
- Bound the list (e.g. max 50 entries; a `review.max_dismissals` knob in `ReviewConfig`, `extra="forbid"`, default 50) — matches the "bounded suppress-list" wording in D-14.
- Parse with a strict regex between the marker comments + `json.loads` + `DismissEntry.model_validate` per item (reject the whole block on malformed JSON, fail-safe = no suppression, never crash — same posture as `parse_severity_from_body` returning None).
- Re-derived every run from the live sticky (no stored parallel state), consistent with D-01.

### Discretion 2 — `/prevue` parser grammar + `author_association` set

**Grammar (strict, line-anchored, untrusted-safe):**
```
command   := "/prevue" WS verb (WS args)?
verb      := "review" | "dismiss" | "resolve"
review    := (no args)
dismiss   := id (WS "reason:" WS reason_text)?
resolve   := id
id        := fingerprint | thread_id
fingerprint := [0-9a-f]{16}                     # exactly the fingerprint() output width
thread_id   := [A-Za-z0-9_=-]{8,}               # GitHub GraphQL node ID charset
reason_text := .{1,500}                          # bounded free text, stored verbatim, never executed
```
- Parse **only the first line** of the comment body that starts with `/prevue` (ignore the rest — prevents multi-command abuse and reduces injection surface).
- Unknown verb / malformed id → reply "unrecognized command; usage: …" and exit 0 (no action). Never raise.
- The parser is a **pure function** `parse_command(body: str) -> Command | None` — ideal TDD unit; test the injection cases (backticks, `$(…)`, newlines, leading whitespace, `/prevue` inside a code block — only honor it at line start).

**`author_association` set + the CONTRIBUTOR edge case (resolved):**
- Workflow `if:` pre-filter: `contains(fromJson('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association)`. This is a *cheap spam filter only*.
- **Authoritative gate (Python):** `repo.get_collaborator_permission(author) in {"write","admin"}`. This is the real authorization.
- **CONTRIBUTOR is NOT in the pre-filter set and is NOT authorized by association** — it means "has committed before", common for external contributors with no write access. A user who happens to be tagged CONTRIBUTOR but truly has write access still passes the authoritative permission gate (the permission API returns `write`), so no legitimate maintainer is locked out. This resolves the locked-decision edge case: rely on the permission API, treat `author_association` as advisory.

### Discretion 3 — Region-snapshot representation (resolved)

**Representation: the `(start, end)` RIGHT-side integer line range** that the shipped `regions_changed` already emits (`positions.py:41`) for the finding's location at dismiss time — stored on `DismissEntry.region` together with `path` and `side`.

- **Why this shape:** `finding_region_changed(finding, regions, context=3)` (the D-09 heuristic) consumes exactly `list[(start,end)]`. Storing the dismissed finding's own region as one `(start,end)` tuple lets the enforcement guard call the *same* predicate against this run's `regions_by_path[path]`: build a stub `Finding(path=entry.path, line=entry.region[0], side=entry.side)` and test `finding_region_changed(stub, this_run_regions)`. If True (a hunk this run overlaps `[start-3, end+3]`), the snapshot is stale → dismissal expires.
- **No new geometry, no new module** — pure reuse of `positions.py`. At dismiss creation, derive the region from the finding's current location (its line ± the local hunk it sits in, taken from `regions_from_comparison`/`regions_changed` on the file's current patch). If a precise hunk range is unavailable at dismiss time (e.g. dismiss issued on a full run with whole-file patches), fall back to `(line, line)` — the C=3 window still gives a sensible expiry zone.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Does the commenter have write access?" | Parse `author_association` and infer | `repo.get_collaborator_permission(login)` → `{write,admin}` | `author_association` is not a permission proxy (Pitfall 1); the permission API is the documented source of truth |
| Resolve the PR from an `issue_comment` | Reconstruct head SHA from refs | `repo.get_pull(issue.number)` then `.head.sha`/`.base.sha` | The payload has no head SHA (Fact 3); one REST call gives SHA + fork guard |
| Region-change detection for dismiss expiry | New overlap math | `finding_region_changed` / `regions_changed` (`positions.py`) | The exact D-09 heuristic is shipped and tested; reuse it (Discretion 3) |
| Dismiss identity | New hashing | `fingerprint(path, title)` (`fingerprint.py`) | Same content-addressed identity as carry-forward; one identity model |
| Suppress-list persistence | A `.github/` file (+`contents: write`) | Fenced block in the sticky (`_upsert_marker_comment`) | Avoids forbidden scope; PR-scoped + base-ref-only for free (Discretion 1) |
| Thread resolution for `/prevue resolve` | REST delete/recreate | `resolve_review_thread` (`graphql.py`) | Best-effort GraphQL resolve already shipped, preserves history |
| Comment-body safety | String-format into a shell `run:` | env var → Python parser, strict grammar | Shell-injection mitigation per GitHub Security Lab (Fact 4) |

**Key insight:** the gap closure adds ~one new workflow YAML, one pure parser, one auth helper, one `DismissEntry` model, and small predicate/flag changes to three shipped functions. Resist building a second state store, a second identity scheme, or a hand-rolled permission check.

---

## Runtime State Inventory

This added scope changes how persistent state is read/written (adds a dismiss record) and adds a new event entry point. Per the refactor protocol:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | The sticky comment. Gap-closure adds a `<!-- prevue:dismiss -->` fenced block to it. Existing PRs have stickies with **no** dismiss block. | **Code edit + self-healing migration:** parse must treat a missing dismiss block as "no dismissals" (empty list). No data migration — the block appears on the next sticky write. Make the block-parser tolerant of absence (return `[]`). |
| Live service config | GitHub PR conversation IS the state (sticky + review threads), accessed via API per run. No external store. | None. |
| OS-registered state | None — ephemeral `ubuntu-latest`; the new `issue_comment` trigger is a workflow definition, not a registered daemon. | None. |
| Secrets/env vars | Reuses `GITHUB_TOKEN`. NEW env vars on the command path: `PREVUE_COMMENT_BODY`, `PREVUE_COMMENT_AUTHOR`, `PREVUE_ISSUE_NUMBER` (or a force-full flag `PREVUE_FORCE_FULL`). No new secret. The engine token (`COPILOT_GITHUB_TOKEN`) is needed on the `/prevue review` path (it runs the engine). | Wire the engine secret through to the command workflow for `review`; `dismiss`/`resolve` need no engine token. |
| Build artifacts | None — pure Python under uv. | None. |

**Canonical question — after every file is updated, what runtime systems still have the old behavior?** Only **open PRs' existing stickies** lack the dismiss block; the tolerant parser self-heals them on the next write. The new `issue_comment` workflow is inert until a `/prevue` comment fires. No other runtime state.

---

## Common Pitfalls

### Pitfall 1: `author_association` treated as a write-access gate (security-critical)
**What goes wrong:** A read-only outside collaborator (`author_association == COLLABORATOR`) is authorized to force reviews and write dismissals; or a legitimate maintainer tagged `CONTRIBUTOR` is locked out.
**Why:** `author_association` encodes *relationship*, not *permission*; GitHub returns it inconsistently (`#643`, `#18690`).
**How to avoid:** Use it only as a workflow `if:` pre-filter; make the authoritative gate `repo.get_collaborator_permission(login) in {write,admin}` in Python before any dispatch (Fact 5).
**Warning signs:** A non-write user successfully runs `/prevue dismiss` in a test.

### Pitfall 2: Reusing `load_pr_context` on the `issue_comment` event (KeyError crash) — see §L1
**What goes wrong:** `load_pr_context` reads `event["pull_request"]` (`client.py:27`), which does not exist on `issue_comment` → `KeyError`, job crashes with no PR feedback.
**How to avoid:** New `load_comment_context()` reading `event["issue"]`/`event["comment"]`, then `repo.get_pull(number)` for the SHA/fork guard.
**Warning signs:** `KeyError: 'pull_request'` on the command workflow.

### Pitfall 3: D-13 resolving threads on budget-skipped files in a full run
**What goes wrong:** On a full run, passing the entire PR file set as `in_scope_paths` to resolve makes a thread on a token-budget-skipped file (NOT actually re-read) get resolved on engine silence — but the engine never saw that file.
**How to avoid:** On full runs, pass `reviewed_paths` (packed files actually sent to the engine), not the whole PR file set, as the authoritative scope (D-13 implementation note).
**Warning signs:** A finding on a large/skipped file silently resolves after a full re-review.

### Pitfall 4: Dismiss block parse failure silently suppressing everything (or nothing)
**What goes wrong:** Malformed JSON in the dismiss block either crashes the run or, worse, is mis-parsed into an over-broad suppression.
**How to avoid:** Fail-safe = empty suppress set on any parse error (no suppression), never crash; validate each entry through `DismissEntry.model_validate`; bound the list. Round-trip test (write block → parse block → equal).
**Warning signs:** A finding that should appear is suppressed with no matching dismiss entry.

### Pitfall 5: Stale dismissal masks a newly-introduced bug (the D-15 raison d'être)
**What goes wrong:** A dismissal persists after the code at that location changed, hiding a real new bug at the same spot.
**How to avoid:** Guard 2 (auto-expire on region change) must run at enforcement time against THIS run's regions; verify a "code changed at dismissed location → finding re-surfaces" fixture.
**Warning signs:** A modified hunk shows no finding where the engine clearly emits one.

### Pitfall 6: `/prevue review` on same-SHA head skipped by the preflight noop gate
**What goes wrong:** The command path inherits the `pull_request` preflight that skips engine install on same-SHA → a forced full review has no engine CLI.
**How to avoid:** The command workflow installs the engine unconditionally (it is human-triggered, intentional cost). Do not reuse the noop preflight on the command path (D-17 note).
**Warning signs:** `/prevue review` produces a degraded/neutral result complaining the engine binary is missing.

### Pitfall 7: Comment body interpolated into a shell `run:` step (script injection)
**What goes wrong:** `${{ github.event.comment.body }}` in a `run:` enables `` `…` ``/`$(…)` injection.
**How to avoid:** Pass via env var, parse in Python (Fact 4).
**Warning signs:** actionlint/zizmor flags template injection on the command workflow.

---

## Validation Architecture

> nyquist_validation enabled; TDD mode on. Reuse the shipped `pytest 9.x + responses 0.26.x` harness.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x + responses 0.26.x (REST + GraphQL HTTP mocking) |
| Config | `pyproject.toml`; `tests/` + `conftest.py` |
| Quick run | `uv run pytest tests/test_<module>.py -x -q` |
| Full suite | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req | Behavior | Type | Command | Exists? |
|-----|----------|------|---------|---------|
| D-13 | Full run resolves engine-silent prior (no region change required); incremental run does NOT (region gate kept) | unit | `uv run pytest tests/test_comments.py -k authoritative_resolve -x` | ❌ Wave 0 (extend) |
| D-13 | Full run does NOT resolve a prior on a budget-skipped (not-reviewed) file | unit | `uv run pytest tests/test_review_flow.py -k full_resolve_scope -x` | ❌ Wave 0 |
| D-13 | Line-shifted same finding (same fingerprint) is NOT resolved | unit | `uv run pytest tests/test_comments.py -k resolve_keeps_present -x` | ❌ Wave 0 |
| D-16 | `parse_command` grammar: review/dismiss/resolve, ids, reason; rejects injection/unknown | unit | `uv run pytest tests/test_commands.py -k parse -x` | ❌ Wave 0 (new file) |
| D-16 | Authorization: write/admin permission → allow; read/none/CONTRIBUTOR-without-write → deny | unit | `uv run pytest tests/test_commands.py -k authorize -x` (responses-mock the permission endpoint) | ❌ Wave 0 |
| D-16 | `load_comment_context` reads issue_comment payload + get_pull head SHA; no `pull_request` KeyError | unit | `uv run pytest tests/test_client.py -k comment_context -x` | ❌ Wave 0 |
| D-16 | Fork PR command refused / no checkout invariant | unit | `uv run pytest tests/test_commands.py -k fork -x` | ❌ Wave 0 |
| D-17 | Force-full ignores marker, resets to head, reconciles via authoritative resolve, re-gates | integration | `uv run pytest tests/test_review_flow.py -k force_full -x` | ❌ Wave 0 |
| D-14 | Dismiss block round-trip (write→parse→equal); tolerant of missing block (→ []) | unit | `uv run pytest tests/test_comments.py -k dismiss_block -x` | ❌ Wave 0 |
| D-15 g1 | Creation gate: reject dismiss of non-existent finding; require reason for 🔴 error | unit | `uv run pytest tests/test_commands.py -k dismiss_create -x` | ❌ Wave 0 |
| D-15 g2 | Auto-expire: region change at dismissed location → finding re-surfaces | unit | `uv run pytest tests/test_review_flow.py -k dismiss_expire -x` | ❌ Wave 0 |
| D-15 g3 | Escalation override: higher severity re-emit → dismissal overridden | unit | `uv run pytest tests/test_review_flow.py -k dismiss_escalate -x` | ❌ Wave 0 |
| D-15 g4 | Suppress-list read only from sticky, never PR head | unit | `uv run pytest tests/test_comments.py -k dismiss_base_only -x` | ❌ Wave 0 |
| D-15 | Suppressed finding dropped from gate but audited in sticky | integration | `uv run pytest tests/test_review_flow.py -k dismiss_audit -x` | ❌ Wave 0 |

### Observable signals (Nyquist)
- **D-13 signal:** after a full `/prevue review`, the count of open Prevue inline threads strictly decreases when the engine stops emitting a prior finding (assert resolved-thread count in a responses-mocked GraphQL fixture).
- **D-15 g2/g3 signals:** a dismissed finding's presence in `apply_gate` input is observable — assert it is absent while untouched/non-escalated, present after region change or escalation.
- **D-16 signal:** unauthorized actor → zero engine invocations, a posted "not authorized" reply; authorized actor → engine invoked exactly once.

### Sampling Rate
- Per task commit: `uv run pytest tests/test_<touched>.py -x -q`
- Per wave merge: `uv run pytest -q`
- Phase gate: full suite green + actionlint/zizmor on the new command workflow before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_commands.py` — NEW: parser grammar, authorization (permission-API mock), fork refusal, dismiss-create gate.
- [ ] `tests/test_client.py` — EXTEND: `load_comment_context` from an `issue_comment` event fixture.
- [ ] `tests/test_comments.py` — EXTEND: authoritative resolve flag, dismiss-block round-trip, base-only read.
- [ ] `tests/test_review_flow.py` — EXTEND: force-full, dismiss expire/escalate/audit, full-resolve scope.
- [ ] `tests/fixtures/` — NEW: `issue_comment_event.json`, collaborator-permission responses (`write`/`read`/`admin`), a sticky body with a dismiss block.
- [ ] CI: add actionlint + zizmor over `.github/workflows/prevue-command.yml`.

---

## Landmines & sequencing constraints (relative to shipped Phase 8)

- **§L1 — `load_pr_context` is PR-event-shaped.** It reads `event["pull_request"]` (`client.py:27`); the `issue_comment` event has no such key. A new `load_comment_context()` is mandatory; do not "fix" `load_pr_context` to branch on event type (keep the PR path clean — add a sibling loader).
- **§L2 — `resolve_outdated_prior_findings` already exists and is wired.** D-13 is a *parameter/predicate* change, not a new function. Don't add a parallel resolve path; thread the `authoritative` flag from `review.py` where `scope` is already known.
- **§L3 — `_open_set_findings` already subtracts `resolved_fingerprints`.** D-13's larger resolved set and D-15's suppression both compose at this seam. Apply dismiss-suppression as an additional subtraction *before* `apply_gate`, after the open set is built — do not duplicate the union logic.
- **§L4 — The shipped preflight noop gate (`prevue-review.yml`) must not bleed into the command path.** `/prevue review` needs an unconditional engine install (Pitfall 6). New workflow, separate install step.
- **§L5 — `min_severity_to_fail: warning` is the dogfood setting** (`.github/prevue.yml`) that turns carried false positives into a red gate. D-13 + D-14/15 are what let the gate go green without per-run manual resolves — verify the end-to-end on PR #16-style fixtures (engine re-emits same fingerprint every run → only a dismiss clears it; engine goes silent on a full run → D-13 clears it).
- **§L6 — Sequencing:** D-13 (pure predicate) → D-14/D-15 dismiss store + guards (pure functions over the open set) → D-16/D-17 `issue_comment` trigger (new surface, security review + live checkpoint). Land in that order so each step is independently testable and the highest-risk surface ships last with the others already green.
- **§L7 — Pre-ship gate (D-16 mandate):** a `checkpoint:human-verify` task must (a) confirm the collaborator-permission gate denies a read-only collaborator on a live sandbox PR, and (b) confirm no PR-head checkout occurs on the command path. This is the "own security review … REQUIRED before ship" the locked decision demands.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `Repository.get_collaborator_permission(login)` returns `none/read/write/admin` and works with `pull-requests: write` / `contents: read` token | Fact 5, D-16 | MEDIUM — if the permission read needs broader scope, add a `checkpoint:human-verify`; method existence is `[VERIFIED]`, the token-scope-for-read is `[ASSUMED]` (collaborator read is normally covered by metadata/contents:read). Verify live. |
| A2 | `issue_comment` job never executes PR-head code as long as no PR-head checkout step is added | Fact 1, threat model | LOW — official docs confirm default-branch ref; the only escape is an added checkout, which the design forbids. |
| A3 | Storing the suppress-list in the sticky satisfies "base-ref-only" (the sticky is bot-authored on the PR conversation, not PR-head content) | Discretion 1, D-15 g4 | LOW — sticky provenance is enforced by `_is_trusted_sticky_actor`; an attacker cannot author a trusted sticky. |
| A4 | Reusing `finding_region_changed` (C=3) for dismiss auto-expire gives correct expiry semantics | Discretion 3, D-15 g2 | MEDIUM — too-wide window expires dismissals prematurely (safe: finding re-surfaces); too-narrow keeps a stale dismissal (the dangerous direction) — C=3 biases toward expiry, the safe side. Tunable. |
| A5 | A single `get_pull(number)` on the command path yields head SHA + fork guard sufficient for D-17 | Fact 3, D-16/D-17 | LOW — same fields `run_review` already uses. |
| A6 | `author_association` pre-filter + permission-API authoritative gate locks out no legitimate maintainer | Discretion 2 | LOW — the permission API is the override; association is advisory only. |

**Net:** the only items needing live confirmation are A1 (permission-read token scope) and A4 (region window tuning) — both covered by the §L7 checkpoint; neither blocks planning.

---

## Sources

### Primary (HIGH confidence)
- Prevue codebase (read this session): `comments.py` (resolve_outdated_prior_findings, derive_prior_findings, parse_severity_from_body, marker, dismiss-surface seam), `graphql.py` (fetch_review_threads/resolve_review_thread), `review.py` (run_review, _open_set_findings, decide_scope wiring), `diff.py` (decide_scope, regions_from_comparison), `positions.py` (regions_changed, finding_region_changed), `gate.py` (apply_gate, ReviewConfig, SEVERITY_RANK), `config.py` (extra="forbid" style), `client.py` (load_pr_context — the PR-event shape), `fingerprint.py`, `.github/workflows/prevue-review.yml`, `.github/prevue.yml`.
- PyGithub 2.9.1 live introspection: `Repository.get_collaborator_permission` and `Repository.get_pull` present `[VERIFIED]`.
- `docs.github.com/en/actions/.../events-that-trigger-workflows` — `issue_comment`: default-branch ref/SHA; `github.event.issue.pull_request` PR discriminator. `[CITED]`
- GitHub Security Lab, "Keeping your GitHub Actions and workflows secure Part 2: Untrusted input" — env-var mitigation for comment-body injection. `[CITED]`

### Secondary (MEDIUM confidence)
- michaelheap.com "Check permissions in a GitHub Actions workflow" — `/repos/{owner}/{repo}/collaborators/{user}/permission` is the reliable write-access check; `author_association` is relationship not permission. `[CITED]`
- GitHub community/issue threads: `actions/github-script#643`, community `#18690`, `#643` — `author_association` returns `CONTRIBUTOR`/`COLLABORATOR` inconsistently vs actual permission. `[CITED]`

### Tertiary (LOW — flagged for live verification)
- Exact token scope required to read the collaborator-permission endpoint from the Actions `GITHUB_TOKEN` (A1) — verify on a live sandbox PR in the §L7 checkpoint.

## Metadata
**Confidence breakdown:**
- D-13 implementation: HIGH — pure predicate change on a shipped, tested function.
- D-14/D-15 storage + guards: HIGH — pure functions reusing shipped fingerprint/region predicates; storage choice is decisive.
- D-16/D-17 `issue_comment` security: MEDIUM-HIGH — official docs + Security Lab confirm the safe pattern; the one correction (permission API over `author_association`) is the load-bearing finding; live permission-scope check pending.

**Research date:** 2026-06-16
**Valid until:** 2026-07-16 (stable APIs; re-verify the collaborator-permission token scope sooner — it is the single live-verification item).
