# Phase 08: Incremental & Stateful Review Lifecycle - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 8 modified + 2 new modules + 2 new test files
**Analogs found:** 12 / 12 (every new symbol has an in-repo analog)

All work is Python in an existing, tested codebase. There are no "no analog" files —
this phase is ~80% scoping/extending tested components plus a few small pure functions
and one thin GraphQL transport module. The analogs below are the exact code to mirror.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/prevue/github/comments.py` (extend) | github I/O | request-response / CRUD | itself (`_upsert_marker_comment`, `post_inline_review`, `SEVERITY_BADGES`) | exact (self-extension) |
| `src/prevue/github/diff.py` (extend) | github I/O | request-response | itself (`fetch_diff`) + `client.get_repo` | exact (self-extension) |
| `src/prevue/github/client.py` (extend) | github client | request-response | itself (`get_authenticated_pull`, `get_repo`) | exact (self-extension) |
| `src/prevue/github/graphql.py` (**NEW**) | github transport | request-response | `client.py` (token/env + PyGithub auth) + best-effort error pattern in `comments._delete_prevue_inline_comments` | role-match |
| `src/prevue/review.py` (extend) | orchestrator | event-driven seam | itself (`run_review`) | exact (self-extension) |
| `src/prevue/gate.py` (extend) | policy/transform | transform | itself (`apply_gate`, `conclude`, `ReviewConfig`) | exact (self-extension) |
| `src/prevue/engines/prompt.py` (extend) | prompt assembly | transform | itself (`build_classify_prompt` UNTRUSTED fencing) | exact (self-extension) |
| `src/prevue/models.py` (extend) | pydantic model | data | itself (`Finding`, `DiffBundle`) | exact (self-extension) |
| `src/prevue/github/positions.py` (extend) | diff parsing | transform | itself (`commentable_lines` unidiff) | exact (self-extension) |
| **NEW: fingerprint helper** | pure util | transform | `gate.py:SEVERITY_RANK` constants + `positions.commentable_lines` (pure-fn style) | role-match |
| **NEW: severity parse-back** | pure util | transform | inverse of `comments.SEVERITY_BADGES` (`comments.py:20`) | exact |
| **NEW: region-changed helper** | pure util | transform | `positions.commentable_lines` (`positions.py:11-31`) | exact |
| `tests/test_fingerprint.py` (**NEW**) | test | — | `tests/test_diff.py` structure / `test_prompt.py` pure-fn classes | exact |
| `tests/test_graphql.py` (**NEW**) | test | — | `tests/test_diff.py` (`responses` HTTP mock) | exact |

## Pattern Assignments

### `src/prevue/github/comments.py` — marker SHA read/write (D-01)

**Analog:** `MARKER` (line 16), `_is_prevue_sticky` (280-284), `_upsert_marker_comment` (287-298).

Keep `MARKER` as the detection prefix; add a SHA-bearing render + tolerant parse. `_is_prevue_sticky`
matches on `.lstrip().startswith(MARKER)` — that prefix check already survives a trailing `head=<sha>`
segment, so detection of legacy AND new markers works unchanged. The upsert is idempotent (re-fetches,
matches by MARKER, edits in place); extend the *body string* only, not the upsert.

Marker constant + render/parse (mirror RESEARCH Code Examples, lines 403-416):
```python
MARKER = "<!-- prevue:sticky -->"                       # keep — detection prefix
MARKER_WITH_SHA = "<!-- prevue:sticky head={sha} -->"
_MARKER_RE = re.compile(r"<!--\s*prevue:sticky(?:\s+head=([0-9a-f]{7,40}))?\s*-->")

def parse_marker_sha(body: str) -> str | None:
    m = _MARKER_RE.search(body or "")
    return m.group(1) if (m and m.group(1)) else None  # None ⇒ no prior SHA ⇒ full review
```
Validate the parsed SHA as `[0-9a-f]{7,40}` (regex already enforces) before it reaches a compare call
(V5 input validation — no path injection into the compare URL).

---

### `src/prevue/github/comments.py` — severity parse-back (D-12)

**Analog:** `SEVERITY_BADGES` (line 20) and `render_inline_comment` (73-89). The rendered first line is
`f"{badge} **{...title...}**"` (line 79). Build the documented inverse, anchored to the **leading badge
emoji only** (most stable element across template versions).
```python
BADGE_TO_SEVERITY = {badge: sev for sev, badge in SEVERITY_BADGES.items()}  # 🔴→error 🟡→warning 🔵→info

def parse_severity_from_body(body: str) -> str | None:
    # scan first line's leading char(s) against BADGE_TO_SEVERITY; return None on no match
    ...
```
**Test contract (round-trip):** `parse_severity_from_body(render_inline_comment(f)) == f.severity` for
every severity. Fail safe on `None` — never silently drop a finding from the open set (Pitfall 4, would
false-green). Add legacy-format and human-comment-no-badge fixtures.

---

### `src/prevue/github/comments.py` — scoped carry-forward + escalation refresh (D-05/D-06)

**Analog:** `post_inline_review` (388-470), specifically the stale-set computation at lines 401-406 and
the upsert/update loop at 412-428. This is a **surgical scoping change, not a rewrite** (RESEARCH "Key insight").

Today (line 401-406) `stale_comments` = every existing Prevue comment whose key is not in `current_keys`.
On an incremental run `current_keys` only covers in-scope files, so unscoped staling wipes valid comments
on untouched files (Pitfall 2). Fix: scope the stale set to in-scope paths.
```python
# D-05: only reconcile comments on files re-reviewed this run.
stale_comments = [
    comment
    for key, comments in existing.items()
    if key[0] in in_scope_paths and key not in current_keys   # key[0] is path
    for comment in comments
]
```
D-06 escalation: in the existing `to_update` branch (415-419), when the prior comment's parsed severity
(via `parse_severity_from_body`) equals the new finding's severity, skip the `.edit()` (keep as-is, no churn);
only edit when severity escalated. Reuse the existing best-effort delete/`GithubException` handling
(`_delete_prevue_inline_comments`, 373-385) for the outdated→resolve fallback when GraphQL fails.

`_existing_prevue_inline_by_location` (362-370) + `_is_prevue_inline_comment` (347-351) are the
re-derivation source for prior fingerprints AND severities — do not enumerate comments any other way.

---

### `src/prevue/github/diff.py` — incremental compare + ancestry (D-02/D-03)

**Analog:** `fetch_diff` (9-28) for the `ChangedFile`/`DiffBundle` mapping; `client.get_repo` (42-45) for repo access.

Add a `decide_scope` pure-ish classifier and an incremental path. The full path (today's `pr.get_files()`)
is retained as first-run / rewritten-history fallback.
```python
def decide_scope(repo, last_sha: str | None, head_sha: str):
    if not last_sha:
        return "full", None
    if last_sha == head_sha:
        return "noop", None
    cmp = repo.compare(last_sha, head_sha)             # PyGithub 2.9.1 Comparison
    if cmp.status == "identical":
        return "noop", None
    if cmp.status == "ahead" and cmp.merge_base_commit.sha == last_sha:
        return "incremental", {f.filename for f in cmp.files}   # in-scope set
    return "full", None                                # diverged/behind ⇒ full + reset marker
```
For in-scope files send the **full current base..head patch** (today's `f.patch` from `pr.get_files()`),
NOT the compare micro-diff — incremental is file-SET level only (D-02 / Pitfall 5). The compare `.files`
identifies *which* files; the per-file patch sent to the engine is still the whole-PR patch.

`DiffBundle` already carries `base_sha`/`head_sha` (`models.py:18-22`) — the only new "since" SHA is the
marker SHA, which flows through `decide_scope`, not the bundle.

---

### `src/prevue/github/graphql.py` (NEW) — thread resolution (D-08/D-10)

**Analog:** `client.py:36-45` (env-token auth: `os.environ["GITHUB_TOKEN"]`, one call per op) +
`comments._delete_prevue_inline_comments` (373-385) for the best-effort log-and-skip error posture.

Prefer a thin raw-`requests` helper (RESEARCH Pattern 2 / Alternatives) over PyGithub internals. Two ops:
a `reviewThreads` query (paginate `first:100`, collect `id`, `isResolved`, `isOutdated`, `path`, `line`,
first comment body) and the `resolveReviewThread` mutation.
```python
GRAPHQL_URL = "https://api.github.com/graphql"

def _graphql(query: str, variables: dict) -> dict:
    resp = requests.post(GRAPHQL_URL, json={"query": query, "variables": variables},
                         headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise GraphQLError(data["errors"])   # caller treats as best-effort: log + skip, NEVER fail run
    return data["data"]
```
**Critical (Open Q #1 / Pitfall 1):** wrap the resolve in best-effort handling — a 403/FORBIDDEN
(possible `contents: write` scope requirement, unverified) must log to stderr and skip, mirroring
`_delete_prevue_inline_comments`. Add a `review.resolve_outdated` config opt-out. Check `isResolved`
from the query before issuing the mutation (idempotency, Pitfall 3).

---

### `src/prevue/engines/prompt.py` — known-issues list (D-07)

**Analog:** `build_classify_prompt` (178-199) — it already fences untrusted paths in a `~~~UNTRUSTED DATA`
block and appends `INSTRUCTION_REASSERTION` (12-16). Mirror this exactly for the known-issues list.

Reuse `_escape_line` (53-55) for each `path + title + line` entry; reuse the `~~~UNTRUSTED DATA … ~~~`
framing seen in `_build_prompt` (115-125). Cap the list at N (default `review.max_known_issues = 20`),
bound to in-scope-file priors only. The list is engine-derived → untrusted (SECR-02). When extending
`_build_prompt`, also update `estimate_prompt_overhead_tokens` (81-100) so packing accounts for it.
```python
known = "\n".join(f"- path={_escape_line(p)} line={ln} title={_escape_line(t)}" for p, ln, t in items[:N])
# inject as its own "## Already reported (do not re-report)" ~~~UNTRUSTED DATA fence, before reassertion
```

---

### `src/prevue/gate.py` — gate over open set (D-11)

**Analog:** `apply_gate` (95-157) and `conclude` (54-72). `conclude` already implements the
failure>neutral>success ladder over *all* findings passed in — the policy needs **no change**; only the
*input* changes. The caller (`review.py`) feeds the union.
```python
open_findings = current_findings + carried_unresolved_priors      # priors re-derived from live comments
open_findings = [f for f in open_findings if f.fingerprint not in resolved_this_run]
gate = apply_gate(open_findings, review_cfg, valid_lines, partial=bool(skipped_files))
```
New config knobs go on `ReviewConfig` (18-36) in the established `model_config = ConfigDict(extra="forbid")`
style: `incremental: bool = True`, `resolve_outdated: bool = True`, `max_known_issues: int = Field(default=20, ge=0)`.

---

### `src/prevue/models.py` — fingerprint field (optional, D-04)

**Analog:** `Finding` (33-40). If findings must carry their fingerprint through the gate union (D-11
dedup `f.fingerprint not in resolved_this_run`), add an optional computed/assigned field consistent with
the existing pydantic `Field` style. `DiffBundle` (18-22) already has `base_sha`/`head_sha` — no change.

---

### NEW: fingerprint / normalize_title (D-04)

**Analog (style):** pure stdlib functions like `positions.commentable_lines` (pure, no I/O) and the
module-level constant style in `gate.py:SEVERITY_RANK`. Place in `comments.py` or a small new helper module
(Claude's discretion).
```python
def normalize_title(title: str) -> str:
    t = unicodedata.normalize("NFKC", title)
    t = t.casefold()                                # NOT .lower() — unicode-correct
    t = re.sub(r"[^\w\s]", "", t, flags=re.UNICODE) # strip punctuation
    return re.sub(r"\s+", " ", t).strip()           # collapse whitespace

def fingerprint(path: str, title: str) -> str:
    return hashlib.sha256(f"{path}|{normalize_title(title)}".encode()).hexdigest()[:16]
```
Test pitfalls: unicode casefold, NFKC equivalence, path normalization (use GitHub's `filename` form),
reworded title = new finding (by design, D-04).

---

### NEW: region-changed helper (D-09)

**Analog:** `positions.commentable_lines` (`positions.py:11-31`) — same `unidiff.PatchSet` parse with the
synthesized `--- a/ +++ b/` header trick (line 17) and the same `is_added`/`is_context`/`is_removed`
target/source line extraction (24-28). Reuse that exact parse style; emit `(start, end)` ranges instead of
a set, then overlap-test against `[line-C, line+C]` with `C=3` (conservative, biases toward NOT resolving).
```python
def finding_region_changed(finding, regions, context: int = 3) -> bool:
    lo, hi = finding.line - context, finding.line + context
    return any(start <= hi and lo <= end for (start, end) in regions)
```

---

### `src/prevue/review.py` — orchestration sequencing (D-01/02/05/07/11)

**Analog:** `run_review` (102-463). Insert the new seam after `pr = get_authenticated_pull(ctx)` (118) and
the skip checks, before `fetch_diff` (133): read sticky body → `parse_marker_sha` → `decide_scope`. The
`packed_files`/classify/pack machinery (lines 133-356) then operates **only over in-scope files** so the
paid LLM fallback never touches out-of-scope files (Discretion: mirror P7 packed-set sequencing). After
`apply_gate` (375), assemble the open-set union (carried priors re-derived from live comments) and the
resolve-outdated pass before `upsert_sticky`. Write the new marker (`head=<head_sha>`) via the existing
`upsert_sticky`/`_upsert_marker_comment` path. The existing failed-inline-key downgrade block (384-406)
and idempotent sticky retry (434-450) are reused as-is.

## Shared Patterns

### Untrusted-data fencing (SECR-02 / V5)
**Source:** `engines/prompt.py` — `INSTRUCTION_REASSERTION` (12-16), `_escape_line` (53-55),
`_safe_diff_block` (47-50), `~~~UNTRUSTED DATA` framing (115-125), and the comment-rendering escapers
`_neutralize_html`/`_escape_inline_markdown`/`_safe_suggestion_block` (`comments.py:28-70`).
**Apply to:** the known-issues list (D-07, engine-derived text) and the severity parse-back (pattern-match
only, never eval). Existing adversarial coverage lives in `tests/test_injection_adversarial.py`.

### Best-effort GitHub I/O (never fail the run on cleanup)
**Source:** `comments._delete_prevue_inline_comments` (373-385) — catch `GithubException`, log `HTTP {status}`
to stderr, continue; and the sticky retry-then-skip in `review.py` (434-450).
**Apply to:** GraphQL `resolveReviewThread` (403/FORBIDDEN → log + skip, D-10/Pitfall 1) and all stale cleanup.

### Idempotent upsert keyed by stable identity
**Source:** `_upsert_marker_comment` (287-298, re-fetch + match by MARKER) and `post_inline_review`
(388-470, upsert by `inline_location_key` = `(path, line, side)`).
**Apply to:** marker SHA write, incremental no-op (`compare.status == "identical"` → refresh marker/check,
no engine run), and resolve (`isResolved` check before mutation). Note (Anti-pattern): inline comments stay
keyed by `(path,line,side)` via `inline_location_key` (354-359); fingerprint is the carry-forward/dedup
identity ONLY — keep the two concerns separate.

### pydantic config in `extra="forbid"` style
**Source:** `gate.py:ReviewConfig` (18-36) with `model_config = ConfigDict(extra="forbid")`, `Field(...)`
bounds, and `@model_validator(mode="after")`; loaded via `load_review_config` (39-51).
**Apply to:** new `review.incremental`, `review.resolve_outdated`, `review.max_known_issues` knobs.

## Test Conventions

**Source:** `tests/test_diff.py` (HTTP via `responses`) and `tests/test_prompt.py` / `tests/test_comments.py`
(pure-fn and `MagicMock` PR objects).

- **REST + GraphQL HTTP mocking:** `@responses.activate` + `responses.add(...)` with `re.compile` URL
  patterns and JSON fixtures (`test_diff.py:30-71`). GraphQL = `responses.POST` to
  `https://api.github.com/graphql`. The `github_env` monkeypatch fixture (22-28) sets
  `GITHUB_EVENT_PATH`/`GITHUB_REPOSITORY`/`GITHUB_TOKEN`.
- **Pure-fn tests:** class-grouped methods, direct call + assert (`test_prompt.py:TestBuildPrompt`).
- **Comment-object tests:** `MagicMock()` PRs/comments (`test_comments.py:TestPostInlineReview`,
  `_finding`/`_gate` helpers); `capsys` to assert best-effort stderr logging.
- **New fixtures (`tests/fixtures/`):** `compare_ahead.json`, `compare_diverged.json`, GraphQL
  `reviewThreads` response, GraphQL resolve response + a 403 error body. Existing fixtures:
  `pulls_files.json`, `event_pull_request.json`, `event_pull_request_fork.json`.
- **New test files:** `tests/test_fingerprint.py`, `tests/test_graphql.py` (mirror `test_diff.py` layout).
  Extend: `test_comments.py`, `test_diff.py`, `test_positions.py`, `test_prompt.py`, `test_gate.py`,
  `test_review_flow.py`.
- **Round-trip contract test (D-12):** `parse_severity_from_body(render_inline_comment(f)) == f.severity`.

## No Analog Found

None. Every file and every new symbol has a concrete in-repo analog (listed above).

## Metadata

**Analog search scope:** `src/prevue/github/`, `src/prevue/engines/`, `src/prevue/`, `tests/`.
**Files scanned:** comments.py, diff.py, client.py, gate.py, prompt.py, models.py, positions.py,
review.py, test_diff.py, test_comments.py, test_prompt.py, tests/fixtures/.
**Pattern extraction date:** 2026-06-15
