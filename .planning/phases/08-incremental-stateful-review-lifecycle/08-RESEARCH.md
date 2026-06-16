# Phase 8: Incremental & Stateful Review Lifecycle - Research

**Researched:** 2026-06-15
**Domain:** Stateful PR-review lifecycle over a stateless GitHub reusable workflow — incremental diff scoping (GitHub compare API), content-addressed finding identity, GraphQL review-thread resolution, gate-over-open-set
**Confidence:** HIGH (code-verified against the installed PyGithub 2.9.1 and the existing prevue codebase) / MEDIUM (the `resolveReviewThread` token-scope question — see Open Questions #1, the dominant risk for this phase)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**LIFE-01 — Incremental scope & state**
- **D-01:** Last-reviewed head SHA lives in the sticky marker — `<!-- prevue:sticky head=<sha> -->`. No separate state block. Finding fingerprints and thread IDs are re-derived from the live PR comments each run (not stored), so there is no parallel state that can drift from the actual comments.
- **D-02:** Incremental at the FILE-SET level. Skip files untouched since the last-reviewed SHA. For each in-scope (changed-since-lastSHA) file, send the engine the full current base..head patch — preserving within-file context, not just the latest micro-hunk. Cross-file call-graph impact stays out of scope.
- **D-03:** Rebase/force-push/squash → full re-review. When the stored SHA is no longer an ancestor of head (detect via compare API status / merge-base), fall back to a full base..head review and reset the marker to head. First run (no marker) → full review. Never review a bogus incremental range.

**LIFE-02 — Finding identity, carry-forward & dedupe**
- **D-04:** Fingerprint = `sha(path | normalize(title))`. Line number, severity, and suggestion text are excluded from identity. `normalize` = lowercase + collapse whitespace + strip punctuation (exact rule = Claude's discretion). Deterministic backstop.
- **D-05:** Carry-forward = scope stale-cleanup to in-scope files only. Today `post_inline_review` deletes ANY prior Prevue comment not in the current finding set (`comments.py:388`). Change it to reconcile only comments on files that were actually re-reviewed this run; comments on out-of-scope files are left fully untouched.
- **D-06:** On a same-fingerprint match: keep the existing comment as-is, except refresh it in place when severity escalated (e.g. warning→error). Cosmetic body/suggestion changes are ignored. Position drift handled by LIFE-04 (D-09).
- **D-07:** Engine dedupe = compact known-issues list + deterministic backstop. Pass the engine a short list of already-reported findings (path + title + line, one line each) with a "do not re-report these" instruction. Bound to prior findings on this run's in-scope files only, with a hard max-N cap (N = Claude's discretion / config knob). Treat the list content as untrusted in the prompt (reuse `prompt.py` fencing — SECR-02 posture).

**LIFE-04 — Outdated thread resolution**
- **D-08:** Resolve outdated threads; delete only own same-run dups. When a prior finding is outdated (D-09), RESOLVE its review thread (GraphQL `resolveReviewThread`). Keep hard-delete only for our own same-run duplicate cleanup.
- **D-09:** Outdated trigger = in-scope file AND line region changed AND fingerprint not in current findings. A still-valid finding on an untouched file is never resolved. Conservative by design.
- **D-10:** GraphQL via a thin helper. `resolveReviewThread` is GraphQL-only. Add a minimal GraphQL request in the `github/` layer to fetch review-thread IDs and resolve them. `pull-requests: write` is expected to cover it — **verify the exact scope in research** (WKFL-04). [SEE OPEN QUESTION #1 — this expectation is NOT confirmed by public sources.]

**Gate verdict on incremental runs**
- **D-11:** Verdict reflects all currently-open findings. The gate evaluates the union of this run's new findings + carried-forward UNRESOLVED prior findings, minus threads resolved by LIFE-04. A clean incremental push cannot turn the check green while an unresolved error comment still stands. Consistent with P7 D-23.
- **D-12:** Carried-forward severity parsed from the existing comment body. Read severity back from the live inline comment's badge (🔴/🟡/🔵, emitted by `render_inline_comment` via `SEVERITY_BADGES`). No extra storage. Make the badge→severity mapping a parseable, tested contract (inverse of `SEVERITY_BADGES`).

### Claude's Discretion
- Exact `normalize(title)` rule and the fingerprint hash function (D-04).
- Known-issues list cap value N and whether it is a `prevue.yml` knob (D-07).
- Whether incremental review is opt-out via config vs always-on (default always-on; a knob like `review.incremental: true` acceptable — match the P6 `extra="forbid"` section style).
- Exact marker SHA format / regex and where the parse/write helper lives (D-01).
- "Line region changed" detection precision (hunk-overlap heuristic) for D-09.
- The classify↔incremental-scope sequencing in `run_review` (mirror the P7 packed-set sequencing principle: paid LLM fallback only touches in-scope files).

### Deferred Ideas (OUT OF SCOPE)
- **LIFE-03 — manual `/review` comment trigger** — stays v2 (separate `issue_comment` trigger surface + its own security review).
- **Cross-file call-graph / semantic impact analysis** — out of scope for this phase and v1 (needs full repo indexing; contradicts the stateless/token thesis).
- **Any non-comment persistence (DB, artifacts)** — stateless workflow.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LIFE-01 | Incremental review on new pushes (diff since last-reviewed SHA, stored in sticky-comment marker) | §"Incremental diff via compare API" (PyGithub `Repository.compare` verified), §"Marker SHA read/write" (extend existing `MARKER`/`_upsert_marker_comment`), §"Rebase/force-push detection" (compare `.status` + merge-base) |
| LIFE-02 | Comment dedupe using existing PR comments as engine context + deterministic fingerprint backstop | §"Finding fingerprint" (normalize + sha256), §"Carry-forward reconciliation" (scope `post_inline_review` stale set), §"Known-issues list" (reuse `prompt.py` fencing) |
| LIFE-04 | Auto-resolve outdated inline threads when underlying lines change | §"GraphQL review-thread resolution" (verified `Requester.graphql_query`/`graphql_named_mutation` native support), §"Line-region-changed detection" (unidiff hunk overlap), §"Severity parse-back" (inverse of `SEVERITY_BADGES`) |
</phase_requirements>

## Summary

Phase 8 turns Prevue's currently-stateless, full-PR-every-push review into a stateful incremental lifecycle while keeping the **only** persistent store the sticky PR comment. Every piece of "state" this phase needs is either (a) one SHA stored in the sticky marker, or (b) re-derived each run from the live PR comments (fingerprints, severities, thread IDs). This is a faithful extension of the project's established "state lives in PR comments, deterministic Python owns writes" pattern (P1) and the "never false-green" gate posture (P7 D-23).

Almost all the machinery already exists in the codebase and only needs **scoping/extension**, not rewriting: `MARKER` + `_upsert_marker_comment` (add `head=<sha>`), `fetch_diff` (add a compare-API path), `post_inline_review` (scope the stale set to in-scope files; swap delete→resolve for the outdated case), `apply_gate` (extend input to the open set), `build_prompt`'s UNTRUSTED-DATA fencing (inject the known-issues list), and `SEVERITY_BADGES` (add a tested inverse). The installed PyGithub 2.9.1 supports everything required: `Repository.compare()` returns a `Comparison` with `.status`/`.ahead_by`/`.behind_by`/`.merge_base_commit`/`.files`, and the internal `Requester` exposes native `graphql_query(query, variables)` and `graphql_named_mutation(...)` — so D-10's assumed raw-`requests` GraphQL helper is **not** required; PyGithub can issue the GraphQL call itself.

**The dominant risk is D-10's permission assumption.** Public sources (a GitHub community discussion, self-reported and reconfirmed across 2023–2026, with no official GitHub staff answer) report that `resolveReviewThread` requires **Contents Read/Write**, not merely `pull-requests: write`. If true, this collides head-on with WKFL-04's minimal-scope posture and the explicit "Out of Scope: requires `contents: write`" prohibition. This must be settled on a live runner before the resolve path is locked, and the design must include a graceful 403-skip and an opt-out so thread resolution can never block the rest of the review.

**Primary recommendation:** Build the deterministic, test-first units first (fingerprint/normalize, severity parse-back, ancestor/diverged classification, hunk-overlap region-changed, gate-over-open-set), wire them into `run_review` in a fixed idempotent order, and gate the GraphQL `resolveReviewThread` path behind a live-runner permission spike + config opt-out so an uncertain scope requirement cannot derail LIFE-01/02.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Read/write last-reviewed SHA | Sticky comment (the only datastore) | `comments.py` (marker parse/write) | D-01: the marker IS the state; deterministic Python owns the write |
| Incremental diff (changed-since-lastSHA file set) | GitHub REST compare API | `diff.py` (`fetch_diff` extension) | D-02: file-set delta is a server-side compare, not a local git op (no checkout) |
| Rebase/force-push detection | GitHub REST compare API (`.status` + merge-base) | `diff.py` | D-03: ancestry is a server-side fact; the compare response carries it |
| Finding identity (fingerprint) | Deterministic Python (pure function) | `models.py`/`comments.py` | D-04: content-addressed, reproducible, no I/O — ideal TDD unit |
| Carry-forward / dedupe reconciliation | `comments.py` (`post_inline_review`) | `review.py` orchestration | D-05/D-06: reconcile against live comments enumerated from the API |
| Known-issues list into prompt | `engines/prompt.py` (UNTRUSTED-DATA fence) | `review.py` (assemble list) | D-07: engine-derived text is untrusted; reuse SECR-02 fencing |
| Outdated thread resolution | GitHub GraphQL (`resolveReviewThread`) | `comments.py`/new `github/graphql.py` helper | D-08/D-10: REST has no resolve; GraphQL only |
| Region-changed detection | Deterministic Python (unidiff hunks) | `positions.py`/new helper | D-09: pure function over parsed hunks — ideal TDD unit |
| Severity parse-back | Deterministic Python (inverse map) | `comments.py` (`SEVERITY_BADGES`) | D-12: pure inverse function — ideal TDD unit |
| Gate over open set | `gate.py` (`apply_gate`) | `review.py` (assemble union) | D-11: verdict policy lives in the gate; input is the union |

## Standard Stack

No new third-party dependencies are required. Everything is already pinned in the project and verified installed.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyGithub | 2.9.1 (installed, verified) | `Repository.compare(base, head)` for incremental diff + ancestry; `Requester.graphql_query` / `graphql_named_mutation` for `resolveReviewThread` | Already the project's GitHub client (STACK.md). Native GraphQL support means no new dependency for D-10. `[VERIFIED: uv run python introspection of installed 2.9.1]` |
| unidiff | 0.7.x (installed) | Parse `files[].patch` hunks for the line-region-changed heuristic (D-09); already used by `positions.py` | Frozen diff format; the project's existing position validator already depends on it. `[VERIFIED: src/prevue/github/positions.py imports PatchSet]` |
| pydantic | 2.13.x | Any new typed model fields (e.g. a fingerprint field on `Finding`, a `review.incremental` config knob) | Project standard; `extra="forbid"` config style established in P6/`gate.py`. `[VERIFIED: src/prevue/gate.py, config.py]` |
| hashlib (stdlib) | — | sha256 for the fingerprint (D-04) | Deterministic, no dependency, cross-platform stable digest. `[ASSUMED — standard practice]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| responses | 0.26.x | Mock the REST compare endpoint + GraphQL POST in unit tests | Existing test pattern (`tests/test_diff.py` registers REST URLs). GraphQL is a `POST https://api.github.com/graphql`. `[VERIFIED: tests/test_diff.py]` |
| pytest | 9.x | Test runner for all the deterministic units | Project standard. `[VERIFIED: tests/]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyGithub native `graphql_query` (internal `Requester`) | Raw `requests.post(https://api.github.com/graphql, ...)` with `GITHUB_TOKEN` (D-10's literal wording) | Raw `requests` is more self-documenting and avoids relying on a PyGithub *internal* (`_Github__requester` / `requester`) that is not part of the public stable API. **Recommendation: prefer a thin raw-`requests` helper** for the GraphQL surface (matches D-10's intent, isolates the GraphQL contract in one tested module, and survives PyGithub internal churn). Use `responses` to mock it identically to REST. |
| `Repository.compare()` (Comparison) | Full-PR diff every run (status quo) | The status quo is exactly what LIFE-01 removes; compare is the file-set delta source. |
| sha256 truncated hex | full sha256 / blake2 / md5 | sha256 truncated (e.g. 16 hex chars) is collision-safe at PR scale, deterministic, stdlib. md5 is fine functionally but avoid for optics. |

**Installation:** None — no new packages.

**Version verification:**
```bash
uv run python -c "import github, unidiff, pydantic; print(github.__version__)"   # 2.9.1 confirmed
```
PyGithub 2.9.1 and unidiff 0.7.x confirmed installed and introspected this session.

## Package Legitimacy Audit

> No external packages are installed by this phase. All libraries (PyGithub, unidiff, pydantic, responses, pytest) are pre-existing, pinned project dependencies verified in STACK.md and confirmed installed via `uv run`. **Package Legitimacy Gate: N/A — no new installs.**

## Architecture Patterns

### System Architecture Diagram

```
GitHub pull_request event (synchronize/opened)
        │
        ▼
  run_review (review.py)  ───────────────────────────────────────────────┐
        │                                                                  │
        ▼                                                                  │
  load_pr_context → fork guard → load_config → should_skip                 │
        │                                                                  │
        ▼                                                                  │
  READ MARKER SHA  ◄── get sticky comment body, parse `head=<sha>`  (D-01) │
        │                                                                  │
        ▼                                                                  │
  DECIDE full vs incremental: (D-03)                                       │
   ┌── no marker / SHA not ancestor of head ──► FULL (base..head), reset   │
   └── SHA is ancestor of head ──────────────► INCREMENTAL (lastSHA..head) │
        │                                                                  │
        ▼                                                                  │
  SCOPED DIFF  (diff.py)                                                    │
   full:        pr.get_files()           (base..head, today's path)        │
   incremental: repo.compare(lastSHA, head).files → in-scope file set,     │
                then send FULL base..head patch for each in-scope file (D-02)
        │                                                                  │
        ▼                                                                  │
  filter / pack / classify  (only over in-scope files — LLM fallback       │
                             never touches out-of-scope files)             │
        │                                                                  │
        ▼                                                                  │
  RE-DERIVE PRIOR STATE from live comments:                                │
   • _existing_prevue_inline_by_location → prior comments                  │
   • fingerprint(prior) (D-04)   • severity parse-back from badge (D-12)   │
   • review-thread IDs via GraphQL query (D-10)                            │
        │                                                                  │
        ▼                                                                  │
  KNOWN-ISSUES LIST → prompt (fenced UNTRUSTED DATA, in-scope priors, ≤N)  │
        │                                                              (D-07)
        ▼                                                                  │
  engine.review → findings → fingerprint(current)                          │
        │                                                                  │
        ▼                                                                  │
  RECONCILE (comments.py):                                                 │
   • carry-forward: stale-cleanup scoped to in-scope files only (D-05)     │
   • same-fp match: keep as-is, refresh only on severity escalation (D-06) │
   • outdated (in-scope ∧ region-changed ∧ fp∉current) → RESOLVE thread D-08/09
   • own same-run dup → delete (existing path)                             │
        │                                                                  │
        ▼                                                                  │
  GATE OVER OPEN SET (gate.py): union(new findings,                        │
        carried-unresolved priors) − resolved-this-run  (D-11)            │
        │                                                                  │
        ▼                                                                  │
  WRITE MARKER head=<new head SHA> + post check run ◄────────────────────┘
```

File-to-implementation mapping is in the Component Responsibilities below; the diagram shows data flow only.

### Recommended Project Structure (extensions, not new top-level layout)
```
src/prevue/
├── github/
│   ├── diff.py          # + incremental compare path + ancestry classification (D-02/03)
│   ├── comments.py      # + marker SHA read/write, fingerprint helper, severity parse-back,
│   │                    #   scoped carry-forward, resolve-instead-of-delete (D-01/04/05/06/08/12)
│   ├── graphql.py       # NEW: thin GraphQL helper — fetch reviewThreads, resolveReviewThread (D-10)
│   └── positions.py     # reused; possibly + region-overlap helper (D-09) or new module
├── review.py            # orchestration sequencing (D-01/02/05/07/11)
├── gate.py              # apply_gate input extended to open set (D-11)
├── engines/prompt.py    # known-issues list injection in UNTRUSTED-DATA fence (D-07)
└── models.py            # optional fingerprint field; DiffBundle already has base/head_sha
```

### Pattern 1: Incremental diff via the compare API (D-02/D-03)
**What:** Use `Repository.compare(lastSHA, head)` to get the file-set changed since the last review. Branch full-vs-incremental on ancestry.
**When to use:** On `synchronize` pushes where a valid marker SHA exists and is an ancestor of head.
**Verified API shape** `[VERIFIED: uv run introspection of PyGithub 2.9.1]`:
```python
# Source: PyGithub 2.9.1 Repository.compare / Comparison (introspected this session)
# REST: GET /repos/{owner}/{repo}/compare/{base}...{head}
comparison = repo.compare(base=last_sha, head=head_sha)   # returns github.Comparison.Comparison
comparison.status            # str: "ahead" | "behind" | "identical" | "diverged"
comparison.ahead_by          # int
comparison.behind_by         # int
comparison.merge_base_commit # github.Commit — the common ancestor
comparison.files             # list[github.File] each with .filename, .status, .patch, .additions
comparison.total_commits     # int
```
- `status == "ahead"` (and `behind_by == 0`) ⇒ `last_sha` IS an ancestor of `head` ⇒ **incremental** is valid; `comparison.files` is exactly the changed-since file set.
- `status in {"diverged", "behind"}` OR `merge_base_commit.sha != last_sha` ⇒ history was rewritten (rebase/force-push/squash) ⇒ **full re-review + reset marker** (D-03).
- `status == "identical"` ⇒ nothing changed since last review ⇒ no new review needed (idempotent re-run; just refresh the marker/check).
- First run (no marker) ⇒ full review (today's `fetch_diff()` path).

`[CITED: docs.github.com/en/rest/commits/commits — compare endpoint status field ahead/behind/identical/diverged]`

**Reliability of the ancestry signal:** `status == "ahead"` is the reliable "lastSHA is an ancestor of head" detector. Cross-check with `merge_base_commit.sha == last_sha` as a belt-and-suspenders assertion — if the merge base is NOT the stored SHA, the stored SHA is not on head's history (rebase) even if some `status` edge case says otherwise. Treat any non-`ahead` status as "fall back to full" — failing safe toward a full review is never wrong, only more expensive.

**Permission/cost:** compare is a single `contents: read` REST call (the project already holds `contents: read`). No new scope. One extra API request per incremental run.

### Pattern 2: GraphQL review-thread resolution (D-08/D-10)
**What:** Two GraphQL operations — a query to fetch review threads (id, isResolved, isOutdated, path, line, first comment), and the `resolveReviewThread` mutation.
**When to use:** For each prior finding determined outdated by D-09.

**Query (fetch thread IDs + state):**
```graphql
# Source: GitHub GraphQL schema (pullRequest.reviewThreads); cross-checked community discussions
query($owner:String!, $repo:String!, $number:Int!, $cursor:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first:100, after:$cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id              # the node ID needed by resolveReviewThread
          isResolved
          isOutdated      # GitHub's own outdated flag — useful cross-check, NOT the trigger
          path
          line
          comments(first:1) { nodes { body author { login } } }
        }
      }
    }
  }
}
```
**Mutation:**
```graphql
mutation($threadId:ID!) {
  resolveReviewThread(input:{threadId:$threadId}) {
    thread { id isResolved }
  }
}
```

**Recommended helper (raw `requests`, isolates the GraphQL contract):**
```python
# Source: GitHub GraphQL API; pattern matches existing responses-based REST tests
import os, requests

GRAPHQL_URL = "https://api.github.com/graphql"

def _graphql(query: str, variables: dict) -> dict:
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        # 403 / FORBIDDEN here is the likely permission-scope failure — caller must
        # treat resolution as best-effort and NOT fail the run (see Open Question #1).
        raise GraphQLError(data["errors"])
    return data["data"]
```
PyGithub's native `Requester.graphql_query(query, variables)` and `Requester.graphql_named_mutation(...)` are also available `[VERIFIED: introspection]`, but they live on the **internal** `_Github__requester` and are not part of the documented public API — prefer the raw helper for stability and test isolation. Map them in `responses` the same way REST is mocked today.

`[CITED: github.com/orgs/community/discussions/24854, /44650 — reviewThreads query shape and resolveReviewThread input]`

### Pattern 3: Content-addressed finding fingerprint (D-04)
**What:** A pure function `fingerprint(path, title) -> str`.
**Recommended concrete rule** (D-04 leaves the exact rule to discretion):
```python
# Source: project convention (deterministic, stdlib only)
import hashlib, re, unicodedata

def normalize_title(title: str) -> str:
    t = unicodedata.normalize("NFKC", title)        # canonical unicode form
    t = t.casefold()                                 # case-insensitive (better than .lower() for unicode)
    t = re.sub(r"[^\w\s]", "", t, flags=re.UNICODE)  # strip punctuation
    t = re.sub(r"\s+", " ", t).strip()               # collapse whitespace
    return t

def fingerprint(path: str, title: str) -> str:
    payload = f"{path}|{normalize_title(title)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]  # 16 hex = 64 bits, collision-safe at PR scale
```
**Pitfalls to encode as tests:** unicode case folding (use `casefold()` not `lower()`), NFKC normalization (so visually-identical titles fingerprint equally), path normalization (compare must use the same `filename` GitHub returns — no leading `./`, forward slashes), and engine rephrasing (accept that a fully reworded title is a *new* finding — this is by design; D-06/D-09 handle the position/dup cases, not semantic rewording).

### Pattern 4: Severity parse-back contract (D-12)
**What:** The inverse of `SEVERITY_BADGES = {"error": "🔴", "warning": "🟡", "info": "🔵"}` (`comments.py:20`), reading severity from a live inline comment body whose first line is `{badge} **{title}**` (per `render_inline_comment`, `comments.py:73`).
```python
# Source: src/prevue/github/comments.py SEVERITY_BADGES / render_inline_comment (verified)
BADGE_TO_SEVERITY = {badge: sev for sev, badge in SEVERITY_BADGES.items()}  # 🔴→error, 🟡→warning, 🔵→info

def parse_severity_from_body(body: str) -> str | None:
    for badge, _ in zip(body[:4], range(1)):  # badge is the leading char of the rendered comment
        ...
    # Robust: scan the first line's leading emoji against BADGE_TO_SEVERITY; return None on no match.
```
**Make it a tested contract:** add a round-trip test asserting `parse_severity_from_body(render_inline_comment(f)) == f.severity` for every severity, plus a "carried-forward comment from a prior version" fixture and a "no badge / human comment" → `None` case. The round-trip test is the guarantee that the inverse survives template changes.

### Pattern 5: Line-region-changed detection (D-09, hunk overlap)
**What:** Decide whether a prior finding's line region was touched between `lastSHA` and `head`. Reuse `unidiff` (already in `positions.py`).
**Recommended heuristic (low false-positive):** A prior finding at `(path, line, side)` is "region changed" if, in the incremental `lastSHA..head` patch for that file, any hunk's affected line range on the finding's side overlaps `[line - C, line + C]` for a small context window `C` (e.g. `C = 3`, matching GitHub's ~3-line diff context). Implementation:
```python
# Source: unidiff PatchSet (same parse style as positions.py:commentable_lines)
def regions_changed(path: str, incremental_patch: str | None) -> list[tuple[int, int]]:
    """Return (start, end) RIGHT-side line ranges touched in the incremental patch."""
    # parse hunks; for each hunk collect target_line ranges of added/context lines
    ...

def finding_region_changed(finding, regions, context: int = 3) -> bool:
    lo, hi = finding.line - context, finding.line + context
    return any(start <= hi and lo <= end for (start, end) in regions)
```
**Why conservative:** D-09 only resolves when ALL three conditions hold (in-scope file AND region changed AND fingerprint not in current findings). The hunk-overlap heuristic governs only the middle condition; a false negative leaves a stale comment (annoying but safe — carry-forward keeps it), a false positive resolves a still-relevant comment (worse). The small context window biases toward NOT resolving — the safe direction. Cross-check against GitHub's own `isOutdated` thread flag from the GraphQL query as an optional secondary signal.

### Anti-Patterns to Avoid
- **Storing fingerprints/thread-IDs/severities anywhere but live comments.** Violates D-01; introduces drift (a deleted comment makes stored state lie). Re-derive every run.
- **Reviewing the bogus `lastSHA..head` range after a force-push.** Produces a nonsense diff; D-03 mandates full re-review when ancestry breaks. Default to full when uncertain.
- **Letting `resolveReviewThread` failure fail the run.** The resolve is a quality-of-life cleanup, not a gate input directly; a 403 (possible scope issue) or transient GraphQL error must be logged and skipped (consistent with the best-effort delete path in `_delete_prevue_inline_comments`).
- **Deleting carried-forward comments on out-of-scope files.** Today's `post_inline_review` deletes any prior comment not in the current finding set (`comments.py:401-406`). On an incremental run the current finding set covers only in-scope files, so the unscoped stale set would wipe every valid comment on untouched files. D-05 fixes exactly this — scope the stale set to in-scope file paths.
- **Re-keying inline comments by fingerprint instead of `(path, line, side)`.** The existing upsert keys on location (`inline_location_key`); fingerprint is the *identity for carry-forward/dedupe decisions*, not the comment placement key. Keep the two concerns separate.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Is lastSHA an ancestor of head?" | Local git rev-list / parent walking via API commit-by-commit | `repo.compare(lastSHA, head).status` + `.merge_base_commit` | One REST call returns ancestry, ahead/behind counts, and the file delta together; no checkout (workflow has no PR-head checkout by design) |
| Diff hunk parsing for region overlap | Regex over `@@` headers | `unidiff.PatchSet` (already a dep, already used in `positions.py`) | Hunk line-number math is the documented multi-day rabbit hole (PITFALLS Pitfall 4); reuse the validated parser |
| Review-thread resolution | REST comment delete/recreate | GraphQL `resolveReviewThread` | REST has no resolve concept; delete loses history (D-08 explicitly chose resolve to preserve it) |
| GraphQL transport | New GraphQL client library | Thin `requests.post` to `/graphql` (or PyGithub's native `graphql_query`) | One mutation + one query; a client library is dependency surface for ~30 lines |
| Comment enumeration / trusted-actor filtering | New enumeration | `_existing_prevue_inline_by_location` + `_is_prevue_inline_comment` (`comments.py:347-370`) | Already enumerates trusted Prevue inline comments — the exact source for re-deriving fingerprints/severities |
| Sticky upsert idempotency | New marker logic | `_upsert_marker_comment` (`comments.py:287`) | Already re-fetches and matches by MARKER so retries don't duplicate; extend the marker string, keep the upsert |

**Key insight:** This phase is ~80% *scoping and wiring existing, tested components*. The genuinely new code is small and pure (fingerprint, normalize, severity parse-back, region-overlap) plus one thin GraphQL module. Resist rewriting `post_inline_review` — D-05/D-06/D-08 are surgical changes to its stale-set computation and its delete-vs-resolve branch.

## Runtime State Inventory

This is a refactor/extension that changes how persistent state is read and written. Per the rename/refactor protocol:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | The sticky comment marker `<!-- prevue:sticky -->` (`comments.py:16`). Phase adds `head=<sha>`. Existing deployed PRs have markers WITHOUT a head SHA. | **Code edit + migration semantics:** parsing must treat a marker with no `head=` as "no prior SHA" → first-run/full-review behavior. No data migration job (stateless); old markers self-heal on next push when the new marker format is written. Make the regex tolerant of both forms. |
| Live service config | None — no external service stores Prevue state. The PR comment thread on GitHub IS the live state, accessed via API each run. | None. |
| OS-registered state | None — runs ephemeral on `ubuntu-latest`; no scheduled tasks, no daemons. | None — verified by the stateless workflow design (REQUIREMENTS "Out of Scope: Full codebase graph/indexing"). |
| Secrets/env vars | `GITHUB_TOKEN` (already used) is the GraphQL credential too. `COPILOT_GITHUB_TOKEN` unchanged. No new secret. | **Verify GITHUB_TOKEN scope covers `resolveReviewThread`** (Open Question #1). No new env var names. |
| Build artifacts | None — no compiled artifacts; pure Python under uv. | None. |

**The canonical question — after every file is updated, what runtime systems still have the old string cached/stored/registered?** Answer: only **already-posted sticky markers on open PRs** carry the old (head-less) marker format. The tolerant-regex requirement above handles them; they upgrade on the next push. No other runtime state exists by design.

## Common Pitfalls

### Pitfall 1: `resolveReviewThread` requires a broader scope than `pull-requests: write`
**What goes wrong:** The GraphQL mutation returns `FORBIDDEN` / "Resource not accessible by integration" at runtime despite `pull-requests: write` being granted, because the mutation reportedly needs **Contents Read/Write**.
**Why it happens:** GitHub's permission mapping for review-thread mutations is undocumented and (per community reports 2023–2026) inconsistent with intuition. The Actions `GITHUB_TOKEN` is an App installation token, so App permission semantics apply.
**How to avoid:** (1) Verify on a live runner with exactly `contents: read, pull-requests: write, checks: write` before locking the design (a `checkpoint:human-verify` task). (2) Wrap resolve in best-effort error handling: on `FORBIDDEN`/any GraphQL error, log to stderr and skip — never fail the run. (3) Add a config opt-out (`review.resolve_outdated: true` default, can be disabled) so consumers unwilling to grant a broader scope can run LIFE-01/02 without LIFE-04. (4) If `contents: write` proves mandatory, escalate to the user: it collides with the explicit "Out of Scope: requires `contents: write`" prohibition — the decision (grant the scope, or ship LIFE-04 as resolve-via-fallback) is the user's, not Claude's.
**Warning signs:** 403 on the GraphQL POST; resolution silently not happening in a live test PR.

### Pitfall 2: Carry-forward stale-cleanup wipes valid comments on untouched files
**What goes wrong:** On an incremental run, `current_keys` covers only in-scope files; the existing unscoped stale-set (`comments.py:401-406`) then marks every comment on out-of-scope files as stale and deletes them.
**Why it happens:** `post_inline_review` was written for full-PR runs where the finding set covered all files.
**How to avoid:** Scope `stale_comments` to keys whose `path` is in the in-scope file set (D-05). Comments on out-of-scope files are neither updated nor deleted — fully untouched.
**Warning signs:** Prior comments vanishing from files the latest push didn't touch; test this with a two-file fixture where push 2 touches only file A.

### Pitfall 3: Re-running the same head SHA (idempotency) double-posts or resolves twice
**What goes wrong:** A workflow re-run (manual re-run, or `synchronize` with no new commits) re-processes; if the marker already equals head, naive logic could re-resolve threads or re-derive a now-empty incremental diff incorrectly.
**Why it happens:** GitHub re-delivers events; CI re-runs are common.
**How to avoid:** Treat `compare(lastSHA, head).status == "identical"` (or `lastSHA == head`) as a no-op review: refresh the marker/check, do not re-run the engine, do not re-resolve. The existing `_upsert_marker_comment` and `post_inline_review` upserts are already idempotent on `(path,line,side)`; keep resolve idempotent by checking `isResolved` from the GraphQL query before issuing the mutation.
**Warning signs:** Duplicate check runs; resolve mutations on already-resolved threads (harmless but wasteful — skip via `isResolved`).

### Pitfall 4: Severity parse-back breaks on carried-forward comments from an older template
**What goes wrong:** A comment posted by a previous Prevue version has a slightly different body layout; the parser returns the wrong severity or `None`, corrupting the gate's open-set severity counts (D-11).
**Why it happens:** The inverse contract depends on the rendered template; templates evolve.
**How to avoid:** Anchor the parser to the **leading severity badge emoji only** (the most stable element — `render_inline_comment` always starts with `{badge} `), not the full line structure. Round-trip test (`parse(render(f)) == f.severity`) plus explicit fixtures for prior-format bodies. On `None`, fail safe: treat unknown severity conservatively (e.g. count as the configured comment threshold or surface as "unknown" rather than dropping it from the open set — never silently make it disappear, which could false-green).
**Warning signs:** Open-set severity counts not matching visible badges in the PR.

### Pitfall 5: Incremental scoping silently drops the within-file context the engine needs
**What goes wrong:** Sending only the micro-hunk changed since `lastSHA` strips the surrounding function/class, degrading review quality.
**Why it happens:** "Incremental" is misread as "only the newest hunk."
**How to avoid:** D-02 is explicit — incremental is at the FILE-SET level: skip untouched files, but for each in-scope file send the **full current `base..head` patch** (today's `pr.get_files()[].patch`), not the `lastSHA..head` micro-diff. The compare API tells you *which* files to include; the per-file patch sent to the engine is still the whole-PR patch for those files.
**Warning signs:** Findings referencing context the engine couldn't have seen; degraded review quality on incremental runs vs full.

### Pitfall 6: Gate false-green on a clean incremental push (the headline correctness risk)
**What goes wrong:** A push that touches only file A (clean) turns the check green while an unresolved `error` comment still stands on file B.
**Why it happens:** `apply_gate` today sees only this run's findings (`gate.py:95`); on an incremental run that excludes file B's prior error.
**How to avoid:** D-11 — feed `apply_gate` the union of this run's new findings + carried-forward UNRESOLVED priors (re-derived from live comments, severity via parse-back), minus threads resolved this run. This extends the P7 D-23 "partial → never green" precedent. The `conclude()` ladder (`gate.py:54`) already does the right thing once its input is the open set.
**Warning signs:** Green check on a PR that still shows an open red-badge Prevue comment.

## Code Examples

### Marker SHA read/write (D-01)
```python
# Source: extend src/prevue/github/comments.py MARKER (verified current value line 16)
import re
MARKER = "<!-- prevue:sticky -->"
MARKER_WITH_SHA = "<!-- prevue:sticky head={sha} -->"
_MARKER_RE = re.compile(r"<!--\s*prevue:sticky(?:\s+head=([0-9a-f]{7,40}))?\s*-->")

def parse_marker_sha(body: str) -> str | None:
    m = _MARKER_RE.search(body or "")
    return m.group(1) if (m and m.group(1)) else None   # None ⇒ no prior SHA ⇒ full review

def render_marker(head_sha: str) -> str:
    return MARKER_WITH_SHA.format(sha=head_sha)
```
Keep `_is_prevue_sticky` matching the marker *prefix* tolerant of the optional `head=` segment so detection still works on both old and new markers.

### Full-vs-incremental decision (D-03)
```python
# Source: PyGithub 2.9.1 Comparison (introspected); diff.py extension
def decide_scope(repo, last_sha: str | None, head_sha: str):
    if not last_sha or last_sha == head_sha:
        return "full" if not last_sha else "noop", None
    cmp = repo.compare(last_sha, head_sha)
    if cmp.status == "identical":
        return "noop", None
    if cmp.status == "ahead" and cmp.merge_base_commit.sha == last_sha:
        return "incremental", {f.filename for f in cmp.files}   # in-scope file set
    return "full", None   # diverged/behind/rewritten history ⇒ full + reset marker
```

### Gate over the open set (D-11)
```python
# Source: src/prevue/gate.py apply_gate (verified signature line 95)
open_findings = current_findings + carried_unresolved_priors  # priors re-derived from live comments
open_findings = [f for f in open_findings if f.fingerprint not in resolved_this_run]
gate = apply_gate(open_findings, review_cfg, valid_lines, partial=bool(skipped_files))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Re-review whole PR every push (`fetch_diff` → `pr.get_files()` base..head) | Incremental file-set delta via `repo.compare(lastSHA, head)`; full only on first run / rewritten history | This phase (LIFE-01) | Dominant token win for active PRs with many pushes (PITFALLS "Re-reviewing the full PR on every synchronize event") |
| Delete any prior comment not in the current finding set | Resolve outdated threads (GraphQL), delete only own same-run dups, carry forward untouched-file comments | This phase (LIFE-02/04) | Preserves history; stops wiping valid comments on incremental runs |
| Gate sees only this-run findings | Gate over union of new + carried-unresolved | This phase (LIFE-11/D-11) | Closes the false-green hole on clean incremental pushes |

**Deprecated/outdated:** none introduced. The existing full-PR path is *retained* as the first-run / rewritten-history fallback (D-03), not removed.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `resolveReviewThread` works with `pull-requests: write` on the Actions `GITHUB_TOKEN` (D-10's expectation) | Pattern 2, Pitfall 1, Open Q #1 | **HIGH** — if `contents: write` is actually required, LIFE-04 collides with the explicit Out-of-Scope `contents: write` prohibition; design must opt-out + escalate. Public sources lean *against* this assumption. |
| A2 | sha256-truncated-16-hex fingerprint is collision-free at PR scale | Pattern 3 | LOW — collisions would merge two distinct findings; 64 bits is ample for ≤thousands of findings per PR. |
| A3 | A small context window (C=3) for hunk-overlap region-changed detection minimizes false resolves | Pattern 5 | MEDIUM — too large resolves still-relevant comments (worse); too small leaves stale comments (safe). Tunable; default conservative. |
| A4 | `compare.status == "ahead"` + `merge_base_commit.sha == last_sha` reliably means lastSHA is an ancestor of head | Pattern 1 | MEDIUM — edge cases (e.g. base branch moved) handled by failing safe to full review. Verify with a force-push fixture. |
| A5 | Old (head-less) markers on existing open PRs parse as "no prior SHA" and self-heal | Runtime State Inventory | LOW — tolerant regex makes this deterministic; worst case is one extra full review on the first post-upgrade push. |
| A6 | Engine title rephrasing produces a new fingerprint (accepted by design) | Pattern 3 | MEDIUM — a reworded title for the same issue posts a "new" comment and the old one may be carried/resolved separately. D-04 explicitly excludes title-semantic matching; acceptable per locked decision. |

## Open Questions (RESOLVED)

> Q1 is resolved-by-design (publicly unanswerable at planning time → best-effort
> + opt-out + a blocking live-runner checkpoint in plan 08-07). Q2/Q3 are resolved
> with concrete defaults adopted into plans 08-03/08-04.

1. **RESOLVED — best-effort + `review.resolve_outdated` opt-out; scope verified live in plan 08-07.** Does `resolveReviewThread` work with the WKFL-04 minimal scope (`pull-requests: write`), or does it require `contents: write`? (D-10 must-verify)
   - What we know: PyGithub 2.9.1 can issue the mutation (native GraphQL + raw `requests` both viable) `[VERIFIED]`. The GraphQL query/mutation shapes are confirmed `[CITED]`.
   - What's unclear: The required token scope. A GitHub community discussion (#44650), self-reported Jan 2023, reconfirmed Feb 2024, with a fresh concern in May 2026 and **no official GitHub staff answer**, states **Contents Read/Write** is required, not `pull-requests: write`. This directly contradicts D-10's expectation and the project's `contents: write` Out-of-Scope prohibition. `[ASSUMED/MEDIUM]`
   - Recommendation: Add a `checkpoint:human-verify` task that runs `resolveReviewThread` on a live sandbox PR with exactly `contents: read, pull-requests: write, checks: write`. Build LIFE-04 with (a) best-effort error handling (403 → log + skip, never fail), and (b) a `review.resolve_outdated` config opt-out so LIFE-01/02 ship independently of the scope answer. If `contents: write` is mandatory, escalate the scope-vs-feature tradeoff to the user.

2. **RESOLVED — `N = 20` via `review.max_known_issues`.** What N (known-issues list cap) and config style? (D-07, Claude's discretion)
   - Recommendation: default `N = 20`, expose as `review.max_known_issues` in the `extra="forbid"` config style matching `ReviewConfig` (`gate.py:18`). Bound the list to in-scope-file priors only; the fingerprint backstop drops any the engine repeats regardless.

3. **RESOLVED — always-on default with `review.incremental: true` knob.** Should incremental be opt-out? (Claude's discretion)
   - Recommendation: always-on default with `review.incremental: true` knob (consumers can force full-PR review). Matches P6 config precedence and the locked-decision guidance.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PyGithub | compare API + GraphQL | ✓ | 2.9.1 (verified installed) | — |
| unidiff | hunk-overlap region detection | ✓ | 0.7.x (verified imported in positions.py) | — |
| GitHub REST compare API | incremental diff + ancestry (D-02/03) | ✓ (covered by existing `contents: read`) | — | full-PR review (status quo) |
| GitHub GraphQL API + `resolveReviewThread` scope | thread resolution (D-08/10) | ⚠️ UNVERIFIED scope | — | **config opt-out + best-effort skip** (Open Q #1) |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** GraphQL `resolveReviewThread` scope is unconfirmed; fallback is the `review.resolve_outdated` opt-out and best-effort 403-skip so LIFE-01/02 remain fully functional without it.

## Validation Architecture

> nyquist_validation is enabled (`workflow.nyquist_validation: true`). TDD mode is on (`tdd_mode: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-cov 7.x + responses 0.26.x (REST + GraphQL HTTP mocking) |
| Config file | `pyproject.toml` (uv-managed); test dir `tests/` with `conftest.py` |
| Quick run command | `uv run pytest tests/test_<module>.py -x -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LIFE-01 | Marker SHA parse/write round-trip (incl. head-less legacy marker → None) | unit | `uv run pytest tests/test_comments.py -k marker_sha -x` | ❌ Wave 0 (extend) |
| LIFE-01 | `decide_scope` returns full/incremental/noop for ancestor / diverged / identical | unit | `uv run pytest tests/test_diff.py -k scope -x` | ❌ Wave 0 (extend) |
| LIFE-01 | compare API maps to in-scope file set (responses-mocked `/compare`) | unit | `uv run pytest tests/test_diff.py -k incremental -x` | ❌ Wave 0 (extend) |
| LIFE-01 | force-push (diverged status / merge-base ≠ lastSHA) → full + marker reset | unit | `uv run pytest tests/test_diff.py -k force_push -x` | ❌ Wave 0 |
| LIFE-02 | `fingerprint`/`normalize_title` determinism: unicode, punctuation, whitespace, path | unit | `uv run pytest tests/test_fingerprint.py -x` | ❌ Wave 0 (new file) |
| LIFE-02 | Carry-forward: stale set scoped to in-scope files; out-of-scope comments untouched | unit | `uv run pytest tests/test_comments.py -k carry_forward -x` | ❌ Wave 0 (extend) |
| LIFE-02 | Same-fingerprint match: keep as-is; refresh only on severity escalation (D-06) | unit | `uv run pytest tests/test_comments.py -k escalation -x` | ❌ Wave 0 |
| LIFE-02 | Known-issues list fenced as UNTRUSTED DATA in prompt; capped at N | unit | `uv run pytest tests/test_prompt.py -k known_issues -x` | ❌ Wave 0 (extend) |
| LIFE-04 | Severity parse-back round-trip (`parse(render(f)) == f.severity`) + legacy/None cases | unit | `uv run pytest tests/test_comments.py -k severity_parse -x` | ❌ Wave 0 (extend) |
| LIFE-04 | Region-changed hunk-overlap: overlap → True, distant change → False, context window | unit | `uv run pytest tests/test_positions.py -k region -x` | ❌ Wave 0 (extend) |
| LIFE-04 | GraphQL query parses thread IDs; resolve mutation issued only for outdated (D-09); 403 → skip, no raise | unit | `uv run pytest tests/test_graphql.py -x` | ❌ Wave 0 (new file) |
| LIFE-04 | Idempotency: already-resolved thread (isResolved) not re-resolved | unit | `uv run pytest tests/test_graphql.py -k idempotent -x` | ❌ Wave 0 |
| D-11 | Gate over open set: clean incremental push with unresolved prior error → not green | unit | `uv run pytest tests/test_gate.py -k open_set -x` | ❌ Wave 0 (extend) |
| LIFE-01/02/04 | End-to-end incremental run wiring in `run_review` (responses-mocked) | integration | `uv run pytest tests/test_review_flow.py -k incremental -x` | ❌ Wave 0 (extend large existing file) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_<touched_module>.py -x -q`
- **Per wave merge:** `uv run pytest -q` (full suite)
- **Phase gate:** full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fingerprint.py` — NEW: fingerprint/normalize determinism (LIFE-02)
- [ ] `tests/test_graphql.py` — NEW: GraphQL query parse + resolve mutation + 403-skip + idempotency (LIFE-04)
- [ ] `tests/test_diff.py` — EXTEND: `decide_scope`, compare-API incremental, force-push fallback (LIFE-01); add a `/compare` responses fixture
- [ ] `tests/test_comments.py` — EXTEND: marker SHA parse/write, severity parse-back round-trip, scoped carry-forward, escalation refresh (LIFE-01/02/04)
- [ ] `tests/test_positions.py` — EXTEND: region-overlap helper (LIFE-04)
- [ ] `tests/test_prompt.py` — EXTEND: known-issues list fencing + cap (LIFE-02)
- [ ] `tests/test_gate.py` — EXTEND: open-set union input (D-11)
- [ ] `tests/test_review_flow.py` — EXTEND: incremental orchestration integration
- [ ] `tests/fixtures/` — NEW fixtures: `compare_ahead.json`, `compare_diverged.json`, GraphQL reviewThreads response, GraphQL resolve response/403

**TDD suitability (clear I/O contracts — test-first):** `normalize_title`/`fingerprint`, `parse_severity_from_body` (round-trip), `decide_scope` (ancestor/diverged/identical classification), `regions_changed`/`finding_region_changed` (hunk overlap), gate-over-open-set (`apply_gate` input union). **Glue code (test via integration):** `run_review` sequencing, the GraphQL transport (mock HTTP), `post_inline_review` scoping changes (extend existing comment tests).

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high`.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Least privilege: do NOT broaden token scope to `contents: write` without explicit user decision (Open Q #1). The stateless-comment trust boundary (P1) is preserved — no new persistence. |
| V5 Input Validation | yes | The known-issues list (D-07) is engine-derived UNTRUSTED text → must go through `prompt.py` UNTRUSTED-DATA fencing + `INSTRUCTION_REASSERTION` (SECR-02). Comment bodies read for severity parse-back are untrusted → parser must not execute/eval, only pattern-match the leading badge. |
| V5 Input Validation | yes | Marker SHA parsed from the sticky body must be validated as `[0-9a-f]{7,40}` before use in a compare API call (no injection into the URL path). |
| V6 Cryptography | yes | sha256 (stdlib hashlib) for fingerprint identity only — not a security primitive; no key material. Never hand-roll a hash. |
| V2/V3/V4 (Auth/Session/Access) | no | No new auth surface; reuses existing `GITHUB_TOKEN`. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via the known-issues list (engine-derived text re-fed into a prompt) | Tampering/EoP | Fence as UNTRUSTED DATA, reuse `_escape_line`/`_safe_diff_block` patterns + `INSTRUCTION_REASSERTION` (SECR-02, already tested in `test_injection_adversarial.py`) |
| Marker SHA injection into compare API URL | Tampering | Validate `[0-9a-f]{7,40}` before constructing the compare call |
| Scope creep to `contents: write` for thread resolution | EoP | Best-effort skip + config opt-out; escalate the scope decision to the user (Pitfall 1) |
| Severity parse-back of a maliciously-crafted comment body to force false-green | Tampering | Anchor parser to leading badge emoji only; fail safe on no-match (never silently drop a finding from the open set) |
| Carried-forward comment wipe (data loss) | DoS (to review signal) | Scope stale-cleanup to in-scope files (D-05) |

## Sources

### Primary (HIGH confidence)
- PyGithub 2.9.1 — live introspection this session (`uv run python`): `Repository.compare` → `Comparison` with `.status`/`.ahead_by`/`.behind_by`/`.merge_base_commit`/`.files`; `Requester.graphql_query(query, variables)` and `graphql_named_mutation(...)` native methods.
- Prevue codebase (verified by reading): `comments.py` (MARKER, `_upsert_marker_comment`, `SEVERITY_BADGES`, `render_inline_comment`, `post_inline_review`, `_existing_prevue_inline_by_location`), `diff.py` (`fetch_diff`), `gate.py` (`apply_gate`, `conclude`), `review.py` (`run_review`), `models.py` (`DiffBundle` base/head_sha), `positions.py` (unidiff usage), `config.py`, `checks.py`, `tests/test_diff.py` (responses pattern).
- `docs.github.com/en/rest/commits/commits` — compare endpoint `status` values (ahead/behind/identical/diverged), `ahead_by`/`behind_by`, `merge_base_commit`.

### Secondary (MEDIUM confidence)
- `github.com/orgs/community/discussions/24854`, `/24850` — `pullRequest.reviewThreads` query shape (id, isResolved, isOutdated, path, line, comments) and `resolveReviewThread` mutation input.
- `.planning/research/PITFALLS.md` — Pitfall 4 (inline position mapping), "Re-reviewing the full PR on every synchronize event" performance trap, idempotency/concurrency checklist.
- `.planning/research/STACK.md` — PyGithub/unidiff capabilities, single-batched-review pattern, minimal-permission posture.

### Tertiary (LOW confidence — flagged for live verification)
- `github.com/orgs/community/discussions/44650` — community self-report (2023, reconfirmed 2024, concern 2026; no GitHub staff answer) that `resolveReviewThread`/`unresolveReviewThread` require **Contents Read/Write**, not `pull-requests: write`. **The single most important claim to verify on a live runner** (Open Q #1 / Pitfall 1).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; all APIs introspected on the installed versions.
- Architecture / sequencing: HIGH — extends existing, tested components; data flow grounded in the actual code.
- Incremental diff + ancestry (LIFE-01): HIGH — compare API shape verified; failing-safe-to-full covers edge cases.
- Fingerprint / severity parse-back / region-overlap (LIFE-02/04 pure units): HIGH — pure functions over verified inputs.
- GraphQL resolve **permission scope** (LIFE-04 / D-10): MEDIUM/LOW — query+mutation HIGH, but the token-scope requirement is unresolved in public sources and must be live-verified; design includes opt-out + best-effort skip to de-risk.

**Research date:** 2026-06-15
**Valid until:** 2026-07-15 (stable APIs; re-verify the `resolveReviewThread` scope question sooner — it is the open risk)
