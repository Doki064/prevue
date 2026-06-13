# Phase 4: Structured Findings & Merge Gate - Research

**Researched:** 2026-06-12
**Domain:** Engine-output JSON parsing/validation, GitHub Reviews API inline placement, Checks API merge gate, severity/budget gating
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Engine JSON contract & degrade ladder (ENGN-03)
- **D-01:** **Single engine response: prose summary + one fenced ```json
  block** containing the findings array matching the `Finding` schema. Parser
  extracts the fence; the prose survives a malformed JSON block — that IS the
  degrade path. Rejected: JSON-only output (one syntax error kills the summary
  too), two engine calls (doubles token spend — against the token thesis).
- **D-02:** **One retry with error feedback.** On missing/invalid JSON block,
  re-invoke the engine once with the validation error + schema reminder
  appended. Bounds worst case at 2x engine spend, then degrade.
- **D-03:** **Salvage valid, drop invalid — per-finding validation.** When JSON
  parses but individual findings fail the pydantic model (bad severity, missing
  path/line), keep the valid ones, drop the rest, record the dropped count in
  the Metadata audit trail (extends Phase 2 D-09 pattern). No coercion of
  near-misses — a misplaced comment is worse than no comment.
- **D-04:** **Final degrade state = prose summary + neutral check + visible
  notice.** Sticky posts the summary as today; Metadata states "structured
  findings unavailable (parse failure)"; check concludes neutral. **Distinct
  failure classes:** engine *parse* failure → neutral (ENGN-03); engine *hard*
  failure (auth, timeout, empty output) keeps Phase 1 D-09 red-run behavior.

#### Verdict & merge-gate semantics (OUTP-03)
- **D-05:** **Default gate behavior: neutral when findings exist.** No findings
  → check concludes `success`; any findings → `neutral` (visible yellow nudge,
  doesn't block). Blocking is opt-in via `min_severity_to_fail`. (User chose
  this over always-green informational.)
- **D-06:** **One conclusion ladder, with or without blocking:**
  `failure` (findings ≥ min_severity_to_fail, when set) > `neutral` (findings
  below threshold, or parse-degrade per D-04) > `success` (no findings).
- **D-07:** **Verdict section mirrors the check exactly** — ✅ Pass / ⚠️
  Findings — not blocking / ❌ Fail — plus severity counts (e.g. "2 error · 3
  warning · 1 info") and the active thresholds. One source of truth; the
  Phase 1 D-05 placeholder is now filled.
- **D-08:** **Verdict vehicle = dedicated Check Run via the Checks API**
  (PyGithub `create_check_run` on the head SHA, named check, conclusions
  success/neutral/failure). Job status can't express neutral. The workflow job
  itself stays green unless the engine hard-fails (D-09 of Phase 1).
- **D-09:** **No-engine-run edge states:** all-files-filtered skip (Phase 2
  D-10) → check `success` with "no reviewable files"; fork no-op → **no check
  created at all** (absence is honest; a required-check setting holds fork PRs
  pending, matching "unsupported").
- **D-10:** **Check Run output panel is compact:** title = verdict + counts;
  summary = thresholds in effect + link to the sticky comment. The sticky stays
  the single rendered source of truth — no duplicated review body.

#### Severity thresholds & config (NOIS-02)
- **D-11:** **Keep the 3-level scale** `error | warning | info` — already the
  locked `Finding` contract (Phase 1 D-02); adapter API must not break.
- **D-12:** **Defaults: `min_severity_to_comment: warning`,
  `min_severity_to_fail` unset.** Info findings never inline by default;
  blocking off out of the box (consistent with D-05 neutral default).
- **D-13:** **Config home: `review:` section in `.github/prevue.yml`** —
  `min_severity_to_comment`, `min_severity_to_fail`, `max_inline_comments`.
  Extends Phase 2's merge_rules surface; trusted-base-ref posture unchanged.
  Workflow-input pass-through is Phase 5's WKFL-03 concern.
- **D-14:** **Sub-comment-threshold findings stay visible:** they appear in the
  sticky summary's findings index and in verdict counts — only inline placement
  is suppressed. Threshold evaluation for neutral/fail considers ALL findings.
  Nothing the engine found is hidden.
- **D-15:** **Fixed severity rubric in the engine prompt** (2-3 lines per
  level: error = correctness/security defect; warning = likely problem or risky
  pattern; info = style/suggestion). Severity drives the gate — unanchored LLM
  severity is too volatile to gate on. Not consumer-overridable (avoids a new
  prompt-injection surface).
- **D-16:** **Invalid threshold config fails closed:** unknown severity value
  or contradictory thresholds raise at startup before any engine spend — red
  run with a clear error. Consumer config error ≠ engine parse failure (D-04
  neutral). Matches Phase 3 D-12 fail-closed posture.

#### Inline placement, fallback & comment budget (OUTP-02, NOIS-03)
- **D-17:** **Invalid-position findings fall back to the sticky summary's
  findings section**, tagged with path:line. Position validity checked against
  diff hunks (unidiff per STACK.md). Rejected: file-level comments (second
  placement mechanism), nearest-line snapping (wrong-line comments mislead).
- **D-18:** **Hard budget default: `max_inline_comments: 10`**, consumer-tunable
  via D-13 config. Overflow findings go to the summary index — nothing lost.
- **D-19:** **Slot allocation: severity rank first, engine emission order
  within a tier.** All errors before warnings (info never inlines per D-12).
  Deterministic given the result; summary notes "N more findings in overview".
- **D-20:** **Batched `create_review(comments=[...])` with event `COMMENT`,
  always.** The Check Run is the only gate; REQUEST_CHANGES would create a
  second sticky gate (bot must re-approve; conversation-resolution friction).
  Never per-finding comment API calls (STACK.md: rate limits, notifications).
- **D-21:** **Uniform inline-comment template (user requirement):** every
  comment renders the same structure from `Finding` fields — line 1: severity
  badge + bold title; then body; then optional "Suggested change" section with
  `Finding.suggestion` as a plain fenced code block (one-click ```suggestion
  blocks deferred to v2 CUST-02); small prevue attribution footer. Python owns
  the markdown rendering, not the engine.
- **D-22:** **4C quality bar in the engine prompt:** finding bodies must be
  Clear, Concise, Correct, Complete — instructed alongside the severity rubric
  (D-15) so the template (D-21) receives consistent content.

#### Summary findings-overview layout
- **D-23:** **Complete index of ALL findings in the sticky** — inlined ones as
  one-line entries, non-inlined ones with full bodies. Verdict counts always
  reconcile against a visible list.
- **D-24:** **Severity-grouped markdown table:** severity badge | path:line |
  title | placement (💬 inline / 📋 summary-only / ⚠️ position-fallback). Rows
  ordered error→warning→info, engine order within tier (mirrors D-19).
- **D-25:** **Non-inlined finding bodies in collapsed `<details>` blocks**
  below the table, keyed by path:line + title, using the same D-21 template.
  Inlined findings get no duplicate body — the inline comment is canonical.
- **D-26:** **Sticky section order: Verdict → prose summary → findings table →
  collapsed details → Metadata.** Preserves the Phase 1 D-04 sectioned shell;
  human narrative first, structured detail after.

### Claude's Discretion
- Parser module location (adapter-internal vs shared `findings` module future
  engines reuse) and the exact JSON-extraction implementation.
- Check Run name string (e.g. `prevue/review`) and whether to set `in_progress`
  status at run start.
- Exact rubric/4C prompt wording, JSON-schema-in-prompt phrasing, and the
  retry feedback message.
- Exact emoji/badge choices and `<details>` summary-line format in templates.
- unidiff usage details for hunk/position validation (RIGHT/LEFT side handling
  for deleted-line findings).
- Where threshold/budget evaluation lives in the pipeline (likely a new
  post-engine stage in `run_review()`).

### Deferred Ideas (OUT OF SCOPE)
- **GitHub one-click ```suggestion blocks** (→ v2, CUST-02): `Finding.suggestion`
  renders as a plain fenced code block in v1 (D-21).
- **Stale inline-comment handling on re-runs** (→ v2, LIFE-04): re-runs post a
  fresh review; auto-resolving outdated threads is lifecycle work.
- **Comment dedupe across runs** (→ v2, LIFE-02): no fingerprinting in v1.
- **Workflow-input config pass-through** (→ Phase 5, WKFL-03): thresholds live
  only in `prevue.yml` for now.
- **Token/cost transparency in summary** (→ Phase 6, OUTP-04): the findings
  table adds placement accounting but not token accounting.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENGN-03 | Engine output is schema-validated with retry-then-degrade handling; a parse failure produces a neutral check, never a crash or false block | JSON-fence extraction pattern (Code Examples §1), per-finding pydantic salvage (§2), retry loop placement in `CopilotCliAdapter.review()` (Architecture Pattern 1), degrade signal via additive `ReviewResult` fields (non-breaking, verified against `models.py`) |
| OUTP-02 | Inline comments via Reviews API, positions validated against diff hunks, invalid positions fall back to summary | unidiff header-synthesis requirement + line-attribute semantics verified empirically against installed 0.7.5 (Pitfall 1, Code Examples §3); PyGithub `create_review(comments=[...])` with `line`/`side` dicts verified against installed 2.9.1 source (Code Examples §4); atomic-422 pitfall makes pre-flight validation mandatory (Pitfall 2) |
| OUTP-03 | Pass/fail/neutral status usable as merge gate, blocking opt-in via severity threshold | PyGithub `repo.create_check_run()` signature verified against installed 2.9.1; neutral conclusion confirmed non-blocking under branch protection (CITED, official docs); head-SHA targeting and `checks: write` permission requirements (Pitfall 3) |
| NOIS-02 | Severity levels with min-severity-to-comment / min-severity-to-fail thresholds | `ReviewConfig` pydantic model pattern (Code Examples §5) extending Phase 2 `load_ruleset()` consumer-yml path; severity rank ordering; D-16 fail-closed validation |
| NOIS-03 | Hard per-review comment budget | Deterministic pipeline ordering (validate → threshold → position-validate → budget-rank, Architecture Pattern 2) so unplaceable findings never consume inline slots |
</phase_requirements>

## Summary

This phase is glue between three verified surfaces: (1) parsing a JSON fence out of Copilot CLI stdout into the existing `Finding` pydantic model, (2) PyGithub's `create_review(comments=[...])` for batched inline comments, and (3) PyGithub's `create_check_run()` for the merge gate. All three API surfaces were verified this session against the **installed** PyGithub 2.9.1 source and the live GitHub REST docs — no version drift risk. The one new dependency is unidiff 0.7.5 (already approved in STACK.md; 13.9M downloads/week), whose behavior against GitHub's `files[].patch` fragments was verified by executing it locally.

Three load-bearing facts shape the plan. First, **unidiff cannot parse GitHub's bare `patch` fragments** — it raises `UnidiffParseError: Unexpected hunk found` unless you synthesize `--- a/{path}\n+++ b/{path}\n` headers; this is a two-line fix but an instant crash if missed. Second, **the Reviews API POST is atomic**: one comment whose `line` is not part of the diff 422s the *entire* batched review — which is exactly why D-17's pre-flight position validation exists, and why it must run before the API call, not as error recovery. Third, **a `neutral` check conclusion is treated as a successful status by branch protection** (official docs: "Successful check statuses are: success, skipped, and neutral") — so D-05's neutral-on-findings default genuinely never blocks, and only `failure` blocks; this confirms the entire conclusion-ladder design is implementable as specified.

The architecture is a new post-engine pipeline stage in `run_review()`: parse/validate (in the adapter, with one retry) → severity partition → position-validate via unidiff → budget-rank → split inline/summary → three GitHub writes (review with inline comments, restructured sticky, check run). Everything stays sync, deterministic, and Python-rendered per the established Phase 1–3 patterns.

**Primary recommendation:** Build the parsing/gating logic as pure functions in two new modules (`engines/parsing.py`, `gate.py` + `github/positions.py`, `github/checks.py`), keep the retry loop inside `CopilotCliAdapter.review()`, signal degrade via additive defaulted fields on `ReviewResult` (non-breaking per D-11), and pre-validate every inline position against synthesized-header unidiff PatchSets before the single atomic `create_review` call.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| JSON-fence extraction + retry | Engine adapter (`engines/`) | — | Only the adapter knows it called the engine and can re-invoke with feedback (D-02); contract output stays `ReviewResult` |
| Per-finding schema validation | Shared parsing module (`engines/parsing.py`) | pydantic `Finding` model | Future engines reuse the prose+fence contract; validation logic must not be Copilot-specific |
| Severity thresholds + budget allocation | Orchestration (`gate.py`, called from `run_review()`) | Config (`ReviewConfig`) | Pure deterministic policy over validated findings; engine-agnostic |
| Position validation | GitHub layer (`github/positions.py`) | unidiff | Validity is defined by the GitHub diff representation, not by the engine |
| Inline comment posting | GitHub layer (`github/` via PyGithub) | — | Python owns all GitHub writes (established Phase 1 pattern) |
| Markdown rendering (inline template, sticky restructure) | GitHub layer (`github/comments.py`) | — | D-21: Python owns rendering, never the engine |
| Check run creation | GitHub layer (`github/checks.py`) | `github/client.py` (repo object) | Checks API is repo-scoped, not PR-scoped; needs `Repository` + head SHA |
| Config loading (`review:` section) | Classify/config layer (`classify/rules.py` path) | pydantic | Reuses Phase 2 consumer-yml loading; fail-closed at startup (D-16) |
| Verdict computation | Orchestration (`gate.py`) | — | Single source of truth consumed by both check run and sticky Verdict section (D-07) |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.13.* (installed) | Per-finding validation (D-03), `ReviewConfig` validation (D-16) | Already the boundary-validation standard in this repo; `Literal` severity + `ValidationError` per item gives salvage-valid-drop-invalid for free [VERIFIED: installed in .venv, pyproject.toml] |
| PyGithub | 2.9.1 (installed) | `pull.create_review(comments=[...])`, `repo.create_check_run(...)` | `ReviewComment` TypedDict supports `path/body/line/side/start_line/start_side`; comment dicts pass through verbatim to `POST /pulls/{n}/reviews`. `create_check_run(name, head_sha, status=, conclusion=, output=)` maps 1:1 to `POST /check-runs`. Both verified by reading the installed 2.9.1 source (`PullRequest.py:544`, `Repository.py:4177`) [VERIFIED: installed source] |
| unidiff | 0.7.5 (**new dep this phase**) | Parse `ChangedFile.patch` hunks for position validation (D-17) | Locked in STACK.md; behavior verified by local execution this session (see Pitfalls). Frozen format, 13.9M weekly downloads [VERIFIED: local execution + pypistats.org] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyYAML | 6.0.* (installed) | Parse `review:` section of consumer `prevue.yml` | Already loaded by `load_ruleset()`; the review section rides the same `yaml.safe_load` |
| `re` + `json` (stdlib) | — | JSON-fence extraction from engine stdout | No library needed; see Don't Hand-Roll re: JSON-repair libs |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| unidiff position validation | Hand-parse `@@` headers with regex | Rejected — STACK.md explicitly warns stdlib/hand-rolled diff handling misses edge cases (no-newline markers, multi-hunk offsets, rename headers); unidiff is locked in D-17 |
| Additive defaulted fields on `ReviewResult` for degrade signal | `engine_meta` dict keys only | Dict keys are stringly-typed; `run_review()` must branch on degrade → typed `degraded: bool = False` + `dropped_findings: int = 0` with defaults is non-breaking per D-11 and self-documenting. Audit detail (retry count, error class) can still live in `engine_meta` |
| Single completed `create_check_run` call | `in_progress` at start + patch to completed | Two-call version risks a permanently dangling `in_progress` check if the engine hard-fails between calls (red run exits before update). Recommend single completed-only call for v1 — atomic, no dangling state (discretion area, resolved) |

**Installation:**
```bash
uv add "unidiff==0.7.*"
```

**Version verification (performed 2026-06-12):**
```bash
# unidiff: PyPI JSON API → latest 0.7.5 (2023-03-10); pypistats → 13.9M/week
# PyGithub 2.9.1, pydantic 2.13.x: already in uv.lock, verified installed in .venv
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| unidiff | PyPI | 12 yrs (0.5 in 2014; 0.7.5 2023-03) | 13.9M/wk (pypistats.org) | github.com/matiasb/python-unidiff | [SUS → cleared] | Approved |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none outstanding — the seam returned `SUS` for unidiff solely on `unknown-downloads` (PyPI's JSON API does not expose download counts). Cross-verified via pypistats.org (13.9M weekly downloads), 12-year release history, and the package is already an approved locked decision in STACK.md/CONTEXT D-17. No `checkpoint:human-verify` needed; no postinstall-script vector exists for pure-Python sdist/wheel installs of this package.

## Architecture Patterns

### System Architecture Diagram

```
                         run_review() pipeline (review.py)
                         ─────────────────────────────────

 fetch_diff ─→ filter ─→ classify ─→ route ─→ skills ─→ build ReviewRequest
                  │                                            │
                  │ (all files filtered)                       ▼
                  ▼                              CopilotCliAdapter.review()
        upsert_skip_note                        ┌──────────────────────────┐
                  │                             │ subprocess → stdout      │
                  ▼                             │ parse fence + validate   │◄─┐
        create_check_run(success,               │   (engines/parsing.py)   │  │ 1 retry w/
          "no reviewable files")                │ invalid? ──────────────────┘ error feedback
                                                │ still invalid → degraded │
                                                │ hard fail → EngineFailure │──→ red run, NO check
                                                └────────────┬─────────────┘     (Phase 1 D-09)
                                                             ▼
                                              ReviewResult(findings, degraded?)
                                                             ▼
                                     NEW post-engine stage (gate.py)
                                  ┌──────────────────────────────────────┐
                                  │ 1. verdict over ALL findings (D-14)  │
                                  │ 2. partition ≥ min_severity_to_comment│
                                  │ 3. position-validate vs unidiff      │
                                  │    (github/positions.py)             │
                                  │ 4. budget-rank placeable findings    │
                                  │    (severity, emission order; D-19)  │
                                  │ 5. split: inline[≤N] / summary-rest  │
                                  └───────┬──────────┬──────────┬────────┘
                                          ▼          ▼          ▼
                              create_review     upsert_sticky   create_check_run
                              (COMMENT,          (Verdict/table/ (success|neutral|
                               comments[])        details/meta)   failure, head SHA)
                              [skip if inline    github/         github/checks.py
                               list empty]        comments.py
```

Fork no-op exits before everything (no check created, D-09). Degraded parse → findings=[], skip create_review, sticky carries notice, check concludes `neutral`.

### Recommended Project Structure

```
src/prevue/
├── engines/
│   ├── copilot_cli.py     # + JSON contract/rubric/4C in _build_prompt(); retry loop in review()
│   └── parsing.py         # NEW: extract_json_fence(), validate_findings() — engine-agnostic
├── gate.py                # NEW: ReviewConfig consumption → verdict, threshold partition, budget allocation
├── github/
│   ├── comments.py        # render_body() restructured (D-26); render_inline_comment() (D-21)
│   ├── positions.py       # NEW: unidiff PatchSet build + (path, line, side) validity check
│   ├── checks.py          # NEW: conclude_check(repo, head_sha, verdict, ...) single completed call
│   └── client.py          # + get_repo(ctx) (Repository object needed for check runs)
├── classify/rules.py      # load_ruleset() grows review: section → ReviewConfig (or sibling loader)
├── models.py              # Finding.severity → Literal; ReviewResult + degraded/dropped_findings defaults
└── review.py              # run_review() wires the new stage + three writes
```

**Module-location discretion resolved:** parsing lives in `engines/parsing.py` (shared, engine-agnostic — future adapters emit the same prose+fence contract); policy lives in `gate.py` at top level (it consumes config + findings, knows nothing about engines or GitHub); GitHub-representation concerns (positions, checks) live under `github/`.

### Pattern 1: Retry-then-degrade inside the adapter

**What:** `CopilotCliAdapter.review()` runs the subprocess, hands stdout to `parsing.parse_review_output()`. On a parse/validation failure of the *fence* (missing fence, malformed JSON, non-list top level), it re-invokes the subprocess once with the error + schema reminder appended to the prompt (D-02), then degrades: returns `ReviewResult(summary_markdown=prose, findings=[], degraded=True)`. Hard failures (`EngineFailure`, auth, timeout, empty stdout) raise as today — the two failure classes never share a code path (D-04).

**When to use:** Any engine adapter implementing the prose+fence contract.

**Key detail:** Per-finding validation failures (D-03 salvage) do NOT trigger retry — retry is only for a missing/unparseable fence. If the fence parses but yields zero valid findings out of N>0 entries, that is salvage with `dropped_findings=N`, not degrade. (Rationale: the contract was honored; the content failed validation. Retrying on content is unbounded coercion territory that D-03 rejects.) The planner may instead choose to retry when *all* findings drop — flag as a plan-level decision; the conservative reading of D-02 ("missing/invalid JSON block") scopes retry to the block itself.

**Prompt-size note:** the retry prompt = original prompt + error appendix; re-check `MAX_PROMPT_BYTES` before the second invocation.

### Pattern 2: Deterministic gate pipeline ordering

**What:** Fixed evaluation order in `gate.py` / `run_review()`:

1. **Verdict first, over ALL valid findings** (D-14: thresholds for neutral/fail consider everything, including info and unplaceable findings).
2. **Comment-threshold partition:** findings ≥ `min_severity_to_comment` are inline *candidates*; the rest are summary-only (📋).
3. **Position-validate candidates** against unidiff hunks; unplaceable candidates become position-fallback (⚠️) summary entries.
4. **Budget-rank the placeable candidates** (severity rank, then emission order; D-19) and take the top `max_inline_comments`; overflow → summary index (📋 with "budget" placement note if desired).

**Why this order:** position-validating *before* budget allocation means an unplaceable finding never burns an inline slot — slot 11 gets promoted. Validating after ranking would silently under-fill the budget.

**When to use:** This exact ordering is the contract between gate.py and the renderers; tests should pin it.

### Pattern 3: Single atomic review POST, conditionally skipped

**What:** One `pr.create_review(body=<one-liner>, event="COMMENT", comments=[...dicts...])` call when the inline list is non-empty; skip the Reviews API entirely when it's empty (zero inline candidates after gating). The top-level `body` is **required** by the REST API when event is `COMMENT` [CITED: docs.github.com/en/rest/pulls/reviews] — use a fixed one-liner pointing at the sticky (D-10 keeps the sticky canonical), e.g. "Prevue posted N inline comments — see the review summary."

**Comment dict shape (passes through PyGithub verbatim to the REST API):**
```python
{"path": f.path, "line": f.line, "side": f.side, "body": rendered_markdown}
```
Never set the legacy `position` key — `line`/`side` is the current API [VERIFIED: PyGithub 2.9.1 `ReviewComment` TypedDict + CITED: REST docs].

### Pattern 4: Check run = repo-scoped single completed call

**What:** `repo.create_check_run(name="prevue/review", head_sha=diff.head_sha, status="completed", conclusion=verdict, output={"title": ..., "summary": ...})`. `head_sha` must be the PR head SHA (already on `DiffBundle.head_sha`, sourced from `pr.head.sha`), never `GITHUB_SHA` (merge commit on `pull_request` events). Re-runs creating a same-name check run on the same SHA are safe: latest wins in the UI [CITED: kenmuse.com/blog/creating-github-checks].

**Discretion resolved:** name `prevue/review` (namespaced, lowercase — selectable by name in branch-protection required checks); no `in_progress` pre-create in v1 (avoids dangling state on hard failure — see Alternatives table).

**Plumbing note:** `client.py` only exposes the `PullRequest`; check runs need the `Repository`. Add `get_repo(ctx)` or return repo alongside pull — one new function, reuses the existing `Github` auth construction.

### Anti-Patterns to Avoid

- **Posting inline comments individually (`create_review_comment` per finding):** N notifications, N API calls, secondary rate limits — explicitly banned in STACK.md and D-20.
- **Nearest-line snapping for invalid positions:** rejected in D-17; wrong-line comments mislead. Fallback to summary, always.
- **Coercing near-miss findings (e.g., mapping severity "ERROR"→"error", string line "12"→12):** D-03 bans coercion. Note: pydantic v2 in default (non-strict) mode WILL coerce `"12"` → `int` — if the planner wants literal-strictness, validate findings with `model_validate(..., strict=True)` or accept lax int coercion as harmless. Severity `Literal` comparison is case-sensitive either way. Flag for the plan: decide strict vs lax explicitly and test it.
- **Routing parse failure through `EngineFailure`:** that is the hard-failure red-run path; parse failure must reach `run_review()` as a degraded-but-successful `ReviewResult` (D-04).
- **Putting the verdict logic in two places:** check conclusion and sticky Verdict section must render from one computed verdict object (D-07).
- **`REQUEST_CHANGES` review event:** creates a second blocking mechanism the bot must dismiss; D-20 locks `COMMENT`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Diff hunk parsing / line-validity sets | Regex over `@@ -a,b +c,d @@` headers | unidiff 0.7.5 | Multi-hunk offsets, `\ No newline at end of file` markers, hunk-count strictness, rename paths — all handled and verified this session |
| "Fixing" malformed engine JSON | json-repair / fuzzy JSON parsers / hand-rolled bracket balancing | D-02 retry with error feedback, then degrade | Repair = coercion, which D-03 explicitly rejects; a repaired-but-wrong finding is a misplaced comment |
| Severity validation & config validation | if/elif string checks | pydantic `Literal["error","warning","info"]` + model validators | Fail-closed (D-16) with precise error messages for free; matches every boundary in this codebase |
| Batched review payload construction | Raw `requests` POST to /reviews | PyGithub `create_review(comments=[...])` | Verified passthrough of `line`/`side` dicts; auth/retries/typing handled |
| Check run REST call | Raw `requests` POST to /check-runs | PyGithub `repo.create_check_run()` | Same — verified signature in installed 2.9.1 |

**Key insight:** every GitHub write in this phase has a verified PyGithub method that maps 1:1 to the REST endpoint; the only genuinely new logic is pure-Python policy (parse, gate, render) — which is exactly the part that should be dependency-free, deterministic functions with table-driven tests.

## Common Pitfalls

### Pitfall 1: unidiff cannot parse GitHub's bare `patch` fragments
**What goes wrong:** `PatchSet(changed_file.patch)` raises `UnidiffParseError: Unexpected hunk found: @@ -1,3 +1,4 @@`.
**Why it happens:** GitHub's `files[].patch` field contains only hunk text (starts at `@@`); unidiff requires `---`/`+++` file headers to open a `PatchedFile` [VERIFIED: local execution of unidiff 0.7.5].
**How to avoid:** Synthesize headers per file: `PatchSet(f"--- a/{f.path}\n+++ b/{f.path}\n{f.patch}")`. Works with paths containing spaces and without a trailing newline (both verified). Files with `patch=None` (large/binary) have no hunks → all findings on them are unplaceable → summary fallback.
**Warning signs:** Any `UnidiffParseError` at runtime — also raised as `Hunk is shorter than expected` if a patch is truncated; wrap PatchSet construction in try/except and treat the file as patch-less (fallback) rather than crashing.

### Pitfall 2: One invalid comment 422s the ENTIRE batched review
**What goes wrong:** `create_review` returns 422 Validation Failed (e.g. `pull_request_review_thread.line must be part of the diff`) and zero comments post — including the valid ones.
**Why it happens:** The Reviews POST is a single atomic API call [CITED: docs.github.com/en/rest/pulls/reviews — 422 documented; atomicity by construction of a single POST].
**How to avoid:** This is the entire reason D-17 pre-flight validation exists. Valid line sets per file, from unidiff: RIGHT side = `{line.target_line_no for added or context lines}`; LEFT side = `{line.source_line_no for removed lines}` (docs: "Use LEFT for deletions… RIGHT for additions… or unchanged lines shown for context"). Validate `(path, line, side)` membership before building the comments array. Also validate `path` is in the diff file set at all — engines hallucinate paths.
**Warning signs:** A 422 from create_review in production means the validator has a gap; log the offending payload shape (not content) and fall back to summary-only for that run rather than crashing (defensive try/except around the POST is cheap insurance consistent with "never a crash").

### Pitfall 3: Check run invisible or on the wrong commit
**What goes wrong:** Check run created but doesn't appear on the PR, or branch protection ignores it.
**Why it happens:** Created against `GITHUB_SHA` (the synthetic merge commit on `pull_request` events) instead of the PR head SHA; or the workflow lacks `checks: write` so the POST 403s.
**How to avoid:** Use `DiffBundle.head_sha` (already `pr.head.sha`). Add `checks: write` to `.github/workflows/review.yml` permissions block — **currently missing** [VERIFIED: read review.yml this session]. Document it for Phase 5's reusable-workflow permissions story (WKFL-04).
**Warning signs:** 403 from create_check_run; check visible in Checks tab but not in the PR merge box.

### Pitfall 4: Treating `neutral` as blocking (or `failure` as the only signal)
**What goes wrong:** Mis-designing the conclusion ladder around a wrong assumption about branch protection.
**Why it happens:** Intuition says "yellow = blocked". Reality: "Successful check statuses are: success, skipped, and neutral" [CITED: docs.github.com troubleshooting-required-status-checks] — neutral NEVER blocks, even for a required check.
**How to avoid:** Exactly the D-05/D-06 design: only `failure` blocks; absence of the check blocks (required check pending) — which is why fork no-op creates no check (D-09). Tests should pin the conclusion mapping table, not GitHub behavior.
**Warning signs:** None at runtime — this is a design-time trap; encode the mapping in one function with a docstring citing the doc.

### Pitfall 5: The JSON fence in untrusted-influenced output
**What goes wrong:** Parser grabs the wrong fenced block — e.g. the engine echoes the schema example in prose before the real findings block, or a prompt-injected diff convinces the engine to emit a decoy block.
**Why it happens:** Naive "first ```json fence" extraction.
**How to avoid:** Instruct the engine to emit exactly one ```json fence as the **last** element of its response, and extract the **last** fence in stdout. Strip the fence from `summary_markdown` so the sticky's prose section never shows raw JSON. Defense-in-depth beyond extraction: path-membership validation (Pitfall 2), severity Literal, budget cap, and length caps bound the blast radius of any injected findings.
**Warning signs:** Sticky prose containing a JSON blob; findings referencing files not in the diff.

### Pitfall 6: pydantic v2 lax mode silently coerces
**What goes wrong:** "No coercion" (D-03) is assumed but `Finding(line="12")` validates fine in default mode.
**Why it happens:** pydantic v2 default (smart/lax) mode coerces numeric strings to int and similar.
**How to avoid:** Decide explicitly in the plan: per-finding validation with `Finding.model_validate(item, strict=True)` enforces literal types; or accept lax coercion for `line` as harmless while severity stays safe (Literal membership is checked either way). Recommend strict=True — it matches D-03's letter and costs nothing. Test both a bad-severity and a string-line finding.
**Warning signs:** Tests pass with obviously-wrong-typed fixtures.

### Pitfall 7: Verdict/sticky/check drift on edge states
**What goes wrong:** Skip path posts a `success` check but the old `upsert_skip_note` body doesn't mention the check; degraded path concludes neutral but Metadata forgets the notice; counts in the Verdict section don't match the findings table.
**Why it happens:** Three render targets (check output, sticky Verdict, sticky table) computed in three places.
**How to avoid:** One verdict/accounting object (conclusion, counts per severity, thresholds in effect, placement tallies, degrade flag, dropped count) computed once in `gate.py` and passed to all renderers. D-23's "counts always reconcile against a visible list" is a property test waiting to happen.
**Warning signs:** Any renderer doing its own counting.

## Code Examples

Verified patterns — sources noted per block.

### 1. JSON-fence extraction (last fence wins)

```python
# Source: stdlib pattern; rationale in Pitfall 5
import json
import re

FENCE_RE = re.compile(r"```json\s*\n(.*?)\n\s*```", re.DOTALL)

def extract_json_fence(stdout: str) -> tuple[str, list | None, str | None]:
    """Return (prose_without_fence, parsed_list_or_None, error_or_None)."""
    matches = list(FENCE_RE.finditer(stdout))
    if not matches:
        return stdout, None, "no ```json fence found in engine output"
    last = matches[-1]
    prose = (stdout[: last.start()] + stdout[last.end():]).strip()
    try:
        payload = json.loads(last.group(1))
    except json.JSONDecodeError as e:
        return prose, None, f"JSON parse error: {e}"
    if not isinstance(payload, list):
        return prose, None, "top-level JSON value must be an array of findings"
    return prose, payload, None
```

### 2. Per-finding salvage validation (D-03)

```python
# Source: pydantic 2.x docs pattern (model_validate + ValidationError per item)
from pydantic import ValidationError
from prevue.models import Finding

def validate_findings(items: list) -> tuple[list[Finding], int]:
    """Keep valid findings, drop invalid; return (valid, dropped_count)."""
    valid: list[Finding] = []
    dropped = 0
    for item in items:
        try:
            valid.append(Finding.model_validate(item, strict=True))  # no coercion, D-03
        except ValidationError:
            dropped += 1
    return valid, dropped
```

With `Finding.severity` tightened to `Literal["error", "warning", "info"]` — same accepted string values as today, so the locked adapter contract (D-11) is preserved while bad severities now fail per-finding.

### 3. Position validity from unidiff (verified by execution against 0.7.5)

```python
# Source: verified locally this session against unidiff 0.7.5
from unidiff import PatchSet
from unidiff.errors import UnidiffParseError

def commentable_lines(path: str, patch: str | None) -> dict[str, set[int]]:
    """Valid (side -> line numbers) for one file's GitHub patch fragment."""
    if not patch:
        return {"RIGHT": set(), "LEFT": set()}
    try:
        # GitHub's files[].patch has no ---/+++ headers; synthesize them.
        ps = PatchSet(f"--- a/{path}\n+++ b/{path}\n{patch}")
    except UnidiffParseError:
        return {"RIGHT": set(), "LEFT": set()}  # treat as unplaceable, never crash
    right: set[int] = set()
    left: set[int] = set()
    for pf in ps:
        for hunk in pf:
            for line in hunk:
                if line.is_added or line.is_context:
                    right.add(line.target_line_no)      # RIGHT: green + white lines
                if line.is_removed:
                    left.add(line.source_line_no)       # LEFT: red lines
    right.discard(None)
    left.discard(None)
    return {"RIGHT": right, "LEFT": left}
```

Verified facts: `line.source_line_no`/`target_line_no` are `None` on the opposite side; `\ No newline at end of file` markers are neither added nor removed (excluded naturally); parsing works without a trailing newline; strict hunk-count validation raises `UnidiffParseError` on truncated patches.

### 4. Batched review + check run (PyGithub 2.9.1, verified against installed source)

```python
# Source: installed PyGithub 2.9.1 — PullRequest.create_review (PullRequest.py:544),
# Repository.create_check_run (Repository.py:4177); REST semantics CITED:
# docs.github.com/en/rest/pulls/reviews, docs.github.com/en/rest/checks/runs
review_comments = [
    {"path": f.path, "line": f.line, "side": f.side, "body": render_inline_comment(f)}
    for f in inline_findings
]
if review_comments:  # never POST an empty review
    pr.create_review(
        body=f"Prevue posted {len(review_comments)} inline comment(s) — see the review summary.",
        event="COMMENT",          # body REQUIRED for COMMENT event (REST docs)
        comments=review_comments, # dicts pass through verbatim; line/side supported
    )

repo.create_check_run(
    name="prevue/review",
    head_sha=diff.head_sha,       # PR head SHA — never GITHUB_SHA (merge commit)
    status="completed",
    conclusion=verdict.conclusion,  # "success" | "neutral" | "failure"
    output={"title": verdict.title, "summary": verdict.summary_md},
)
```

### 5. ReviewConfig with fail-closed validation (D-13/D-16)

```python
# Source: pydantic 2.x standard pattern; mirrors Phase 2 RuleSet fail-closed posture
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["error", "warning", "info"]

class ReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # typo'd keys fail closed (D-16)

    min_severity_to_comment: Severity = "warning"   # D-12 default
    min_severity_to_fail: Severity | None = None    # blocking off by default
    max_inline_comments: int = Field(default=10, ge=0)  # D-18; 0 = summary-only mode
```

Loaded from the consumer dict's `review:` key alongside the existing `load_ruleset()` consumer read — same trusted-base-ref posture, validation errors raise before any engine spend. Severity rank for comparisons: `{"error": 0, "warning": 1, "info": 2}` (lower = more severe); a finding meets a threshold when `rank(sev) <= rank(threshold)`.

### 6. Conclusion ladder (D-05/D-06) — single source of truth

```python
# Source: design from CONTEXT D-05/D-06; neutral-doesn't-block CITED:
# docs.github.com troubleshooting-required-status-checks
def conclude(findings: list[Finding], cfg: ReviewConfig, degraded: bool) -> str:
    """failure > neutral > success. Branch protection treats neutral as passing."""
    if degraded:
        return "neutral"                      # D-04 parse-degrade
    if cfg.min_severity_to_fail is not None and any(
        SEVERITY_RANK[f.severity] <= SEVERITY_RANK[cfg.min_severity_to_fail]
        for f in findings
    ):
        return "failure"                      # opt-in blocking
    if findings:
        return "neutral"                      # D-05 default nudge — never blocks
    return "success"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Review comments by `position` (offset from hunk header) | `line` + `side` (absolute blob line) | GraphQL/REST comfort APIs, 2019+; `position` now legacy in docs | Use `line`/`side` exclusively; never compute hunk offsets |
| Commit status API (`/statuses`) for gates | Checks API check runs (rich output, neutral conclusion) | Checks API GA 2018 | `neutral` exists only on check runs — required for D-05 |
| Engine returns prose, bot regexes for file:line mentions | Structured JSON contract + schema validation | Standard practice for review bots | This phase implements it; retry-then-degrade bounds cost |

**Deprecated/outdated:**
- `position` parameter in review comments: legacy; still accepted but superseded by `line`/`side` [CITED: REST docs mark position as the older mechanism].
- Per-comment `create_review_comment` loops: banned in STACK.md (rate limits, notification spam).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Reviews POST being atomic means one invalid `line` rejects all comments (inferred from single-POST semantics + documented 422; not reproduced live this session) | Pitfall 2 | Low — pre-flight validation is required by D-17 regardless; if GitHub partially accepted, behavior would only improve |
| A2 | GITHUB_TOKEN-created check runs attach to the Actions app check suite (grouped under the workflow in the Checks tab) but remain individually selectable as required checks by name | Pitfall 3 / Pattern 4 | Low-medium — cosmetic grouping; if name-based required-check selection failed, the merge-gate story changes. Mitigate: verify on the live test PR during phase verification (community sources consistent: kenmuse.com, LouisBrunner/checks-action) |
| A3 | Copilot CLI reliably honors "emit exactly one ```json fence at the end" formatting instructions often enough that the 1-retry budget suffices | Pattern 1 | Medium — if fence compliance is poor, degrade rate is high (still safe: neutral + summary, never a false block). Mitigate: live test PR in verification; prompt wording is discretionary and tunable |
| A4 | `side="LEFT"` comments on removed lines work through the batched reviews endpoint the same as the single-comment endpoint where `side` is documented | Pattern 3 | Low — `ReviewComment` TypedDict includes `side`; REST docs document the fields on the reviews endpoint with semantics detailed on the comments endpoint |

## Open Questions

1. **Should "all findings dropped in salvage" trigger the D-02 retry?**
   - What we know: D-02 scopes retry to "missing/invalid JSON block"; D-03 scopes salvage to per-finding failures with no retry mentioned.
   - What's unclear: a fence that parses to N entries, all invalid, honors the block contract but yields nothing.
   - Recommendation: do NOT retry (conservative reading; bounded spend), record `dropped_findings=N` in Metadata, findings=[] → verdict `neutral`-if-degraded does NOT apply (not degraded; it's a valid empty result → `success`? No —) **planner must decide**: recommend treating 0-valid-of-N>0 as *degraded* (neutral + notice) since gating `success` on fully-dropped output would be a false green. This is the one semantic seam CONTEXT doesn't pin.

2. **Does the sticky's findings table need a distinct placement tag for budget-overflow vs sub-threshold entries?**
   - What we know: D-24 defines 💬 inline / 📋 summary-only / ⚠️ position-fallback.
   - What's unclear: budget overflow is neither sub-threshold (it qualified) nor position-invalid.
   - Recommendation: render overflow as 📋 summary-only with the D-19 "N more findings in overview" note in the inline review body/sticky; no fourth icon needed. Cosmetic — planner's call.

3. **`commit_id` on create_review:** defaults to the most recent PR commit [CITED: REST docs]. The concurrency group cancels superseded runs, so the default is acceptable; passing the reviewed head SHA explicitly (via `repo.get_commit(head_sha)`, one extra API call) is stricter against push races. Recommend the explicit commit only if the planner wants belt-and-braces; default is fine for v1.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | runtime | ✓ | 3.13 (.venv) | — |
| uv | dep management | ✓ | 0.11.x (lockfile) | — |
| pydantic | validation | ✓ | 2.13.* installed | — |
| PyGithub | reviews + checks | ✓ | 2.9.1 installed | — |
| unidiff | position validation | ✗ (not in pyproject) | 0.7.5 on PyPI, verified | none needed — `uv add "unidiff==0.7.*"` is a task |
| `checks: write` permission | check run POST | ✗ (review.yml lacks it) | — | add to workflow permissions block — task, not blocker |
| Copilot CLI / live PR | end-to-end verification only | CI-only | @github/copilot 1.0.61 pinned in review.yml | unit tests + responses fixtures locally; live test PR for UAT |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** unidiff (install task), `checks: write` (one-line workflow edit).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.* + pytest-cov 7.* + responses 0.26.* (all installed) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests) |
| Quick run command | `uv run pytest -x -q` |
| Full suite command | `uv run pytest --cov=prevue` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENGN-03 | Fence extraction, salvage, retry-once, degrade-to-neutral, hard-fail stays red | unit | `uv run pytest tests/test_findings_parsing.py -x` | ❌ Wave 0 |
| ENGN-03 | Adapter retry loop (subprocess mocked twice, second prompt contains error) | unit | `uv run pytest tests/test_copilot_adapter.py -x` | ✅ extend |
| OUTP-02 | unidiff validity sets (added/context RIGHT, removed LEFT, patch=None, malformed patch) | unit | `uv run pytest tests/test_positions.py -x` | ❌ Wave 0 |
| OUTP-02 | Batched create_review payload shape; skip-when-empty; fallback rows in sticky | unit (responses mock) | `uv run pytest tests/test_review_flow.py tests/test_comments.py -x` | ✅ extend |
| OUTP-03 | Conclusion ladder table (degraded/fail-threshold/findings/none); check-run payload incl. head_sha | unit | `uv run pytest tests/test_gate.py tests/test_checks.py -x` | ❌ Wave 0 |
| NOIS-02 | ReviewConfig defaults, Literal rejection, extra-key fail-closed, threshold partition incl. D-14 all-findings verdict | unit | `uv run pytest tests/test_gate.py -x` | ❌ Wave 0 |
| NOIS-03 | Budget cap honored after position validation; promotion of slot N+1; deterministic D-19 ordering | unit | `uv run pytest tests/test_gate.py -x` | ❌ Wave 0 |
| all | Live E2E: real PR posts inline comments + check run in sandbox | manual-only (needs Copilot token + live repo) | test PR, per Phase 1 precedent | UAT step |

### Sampling Rate
- **Per task commit:** `uv run pytest -x -q`
- **Per wave merge:** `uv run pytest --cov=prevue`
- **Phase gate:** Full suite green before `/gsd-verify-work`; live test PR for inline-placement + check-run visibility (A2/A3 assumptions)

### Wave 0 Gaps
- [ ] `tests/test_findings_parsing.py` — ENGN-03 (fence/salvage/degrade)
- [ ] `tests/test_positions.py` — OUTP-02 (unidiff validity sets; fixture patches incl. new-file `@@ -0,0`, deletions, no-newline marker)
- [ ] `tests/test_gate.py` — NOIS-02/NOIS-03/OUTP-03 (config, partition, budget, verdict)
- [ ] `tests/test_checks.py` — OUTP-03 (check-run payload via responses mock)
- [ ] `uv add "unidiff==0.7.*"` before any positions test runs

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (unchanged) | existing GITHUB_TOKEN / fine-grained PAT guard from Phase 1 |
| V3 Session Management | no | stateless workflow run |
| V4 Access Control | yes | `checks: write` is the only new scope — add explicitly, keep least-privilege block auditable (WKFL-04 groundwork) |
| V5 Input Validation | yes | pydantic strict per-finding validation; `ReviewConfig` extra="forbid"; path-membership check against diff file set |
| V6 Cryptography | no | none introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt-injected diff makes engine emit attacker-authored findings | Tampering/Spoofing | Existing untrusted-data fencing (Phase 1); fixed non-overridable rubric (D-15); path-in-diff validation; budget cap (D-18) bounds volume; severity Literal bounds gate impact; SECR-02 hardening continues in Phase 6 |
| Markdown injection via finding title/body into sticky table | Tampering | Escape `|` and newlines in table cells; render `suggestion` inside a fence with backtick-escaping (reuse the `_safe_diff_block` 4-backtick pattern); cap field lengths in the Finding/render layer (GitHub comment hard limit 65,536 chars) |
| Decoy ```json fence smuggled through engine output | Tampering | Last-fence extraction + instruct fence-at-end (Pitfall 5); validation bounds damage |
| Consumer config as attack surface (malformed `review:` keys) | Elevation | Fail-closed pydantic at startup before engine spend (D-16); trusted-base-ref read posture unchanged |
| Token leakage in new error paths (check-run/review 4xx) | Information Disclosure | Reuse Phase 1 `_sanitize_stderr`-style redaction discipline in any new exception messages; PyGithub exceptions can echo request context — wrap and re-raise with sanitized messages |
| False merge-approval (gate says success on bad data) | Repudiation/Tampering | Verdict computed over ALL validated findings (D-14); fully-dropped salvage should not conclude `success` (Open Question 1 recommendation) |

## Project Constraints (from CLAUDE.md)

- **Stack locked:** Python 3.12 floor, PyGithub 2.9.1, pydantic 2.13.x, unidiff 0.7.5, PyYAML 6.x — research conforms; only unidiff is newly installed.
- **"What NOT to Use" honored:** no per-finding `create_review_comment` loops (single batched `create_review` with `comments[]`); no LangChain/agent frameworks (pure subprocess + pydantic); no `pull_request_target`; no `secrets: inherit`.
- **Stack pattern honored:** adapter contract stays the pydantic `ReviewRequest → ReviewResult` pair; adapters stay sync; `metadata_only=True` unidiff escape hatch noted (not needed — full parse required for line iteration).
- **Minimal permissions constraint:** new `checks: write` scope is within the documented intended scope set ("read contents, write PR comments/checks"); must be added explicitly to `review.yml` and documented.
- **GSD workflow enforcement:** implementation happens via `/gsd-execute-phase`; this document plans only.
- **pathspec 1.x / pydantic v2-only / uv pinning conventions:** unchanged by this phase.

## Sources

### Primary (HIGH confidence — verified via tool against authoritative artifacts)
- Installed PyGithub 2.9.1 source (`.venv/.../github/PullRequest.py:544` create_review + `ReviewComment` TypedDict; `Repository.py:4177` create_check_run) — signatures, passthrough semantics
- unidiff 0.7.5 executed locally (uv-installed, isolated) — header requirement, Line attributes, edge cases (bare hunk failure, no-trailing-newline, `@@ -0,0`, no-newline marker, space paths)
- Repo code read this session: `models.py`, `review.py`, `copilot_cli.py`, `comments.py`, `client.py`, `rules.py`, `cli.py`, `diff.py`, `base.py`, `review.yml`, `pyproject.toml`, tests/ listing
- PyPI JSON API + pypistats.org — unidiff 0.7.5 latest, 13.9M weekly downloads

### Secondary (MEDIUM confidence — official docs via WebFetch)
- docs.github.com — troubleshooting-required-status-checks ("Successful check statuses are: success, skipped, and neutral")
- docs.github.com/en/rest/pulls/reviews — comments[] fields, body required for COMMENT, commit_id default, 403/422
- docs.github.com/en/rest/pulls/comments — line/side/start_line semantics, LEFT for deletions
- agentskills/STACK.md project research (project-level, previously verified 2026-06-12)

### Tertiary (LOW-MEDIUM confidence — community, cross-checked)
- kenmuse.com/blog/creating-github-checks — GITHUB_TOKEN check creation, same-name latest-wins, head.sha guidance (consistent with official docs; check-suite grouping detail → Assumption A2)
- WebSearch corroboration (LouisBrunner/checks-action, GitHub docs on GITHUB_TOKEN auth)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library installed and inspected, or executed locally; the single new dep is pre-approved and registry-verified
- Architecture: HIGH — all integration seams read directly from existing code; CONTEXT.md pins 26 decisions, discretion areas resolved with rationale
- Pitfalls: HIGH for unidiff/API mechanics (verified/cited); MEDIUM for GITHUB_TOKEN check-suite cosmetics and Copilot fence-compliance rate (Assumptions A2/A3 — covered by live-PR verification step)

**Research date:** 2026-06-12
**Valid until:** ~2026-07-12 (GitHub REST surfaces and unidiff are stable; Copilot CLI behavior is the fast-moving element — re-verify fence compliance at execution)
