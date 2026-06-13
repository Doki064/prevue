# Phase 4: Structured Findings & Merge Gate - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn the engine's prose-only review into trustworthy, bounded structured output:
the Copilot adapter returns schema-validated `Finding` objects (the ENGN-01
contract locked in Phase 1), valid findings post as correctly-placed inline
comments via the Reviews API, findings carry consumer-configurable severity
thresholds, a hard comment budget caps inline volume, and a dedicated GitHub
Check Run reports pass/fail/neutral usable as a merge gate. A parse failure
degrades to summary-only + neutral check — never a crash or false block.

Requirements: ENGN-03 (schema-validated, retry-then-degrade), OUTP-02 (inline
comments, position-validated, summary fallback), OUTP-03 (pass/fail/neutral
merge gate, blocking opt-in), NOIS-02 (severity thresholds), NOIS-03 (hard
comment budget).

**Explicitly later phases:** reusable workflow packaging + workflow-input
config pass-through (WKFL-* → Phase 5); LLM fallback classification (CLSF-02 →
Phase 5); token/cost transparency + budget packing (OUTP-04, DIFF-03 → Phase
6); GitHub one-click `suggestion` blocks (CUST-02 → v2); incremental review,
comment dedupe, auto-resolve stale threads (LIFE-* → v2).

</domain>

<decisions>
## Implementation Decisions

### Engine JSON contract & degrade ladder (ENGN-03)
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

### Verdict & merge-gate semantics (OUTP-03)
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

### Severity thresholds & config (NOIS-02)
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

### Inline placement, fallback & comment budget (OUTP-02, NOIS-03)
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

### Summary findings-overview layout
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Stack & platform facts
- `.planning/research/STACK.md` — verified deps for this phase: **unidiff
  0.7.5** (PatchSet → files → hunks → lines for inline position validation;
  de-facto standard for review bots), **PyGithub 2.9.1**
  (`pull.create_review(comments=[...])` batched inline comments,
  `repo.create_check_run()` pass/fail check), **pydantic 2.13.4** (Finding
  schema validation at the engine boundary). "What NOT to Use": never post
  inline comments individually (`create_review_comment` per finding — N
  notifications, secondary rate limits).

### Project specs
- `.planning/REQUIREMENTS.md` — ENGN-03, OUTP-02, OUTP-03, NOIS-02, NOIS-03
  definitions; v2 deferrals (CUST-02 suggestion blocks, LIFE-* lifecycle).
- `.planning/PROJECT.md` — pipeline definition, minimal-permissions constraint
  (`checks: write` now exercised), output decision (summary + inline + check).
- `.planning/phases/01-walking-skeleton-review-loop/01-CONTEXT.md` — Phase 1
  decisions this phase completes: D-01 (structured findings deferred to here),
  D-02 (locked adapter contract — must not break), D-04/D-05 (sticky shell,
  Verdict placeholder now filled), D-09 (fail-closed engine hard failure —
  preserved, now distinct from parse-failure-neutral).
- `.planning/phases/02-zero-token-classification-routing/02-CONTEXT.md` —
  D-05 consumer `prevue.yml` config pattern the `review:` section extends;
  D-09 Metadata audit-trail pattern; D-10 skip path (now gets a success check).
- `.planning/phases/03-selective-skill-loading/03-CONTEXT.md` — D-13 loaded-
  skills Metadata (coexists with new findings audit fields).

### Existing code (Phases 1–3)
- `src/prevue/models.py` — `Finding` (path/line/side/severity/title/body/
  suggestion) and `ReviewResult` — the locked contract this phase finally
  populates and validates.
- `src/prevue/engines/copilot_cli.py` — `_build_prompt()` (JSON contract +
  rubric + 4C instructions land here), `review()` (retry loop wraps the
  subprocess call), `EngineFailure` (hard-failure class stays red-run).
- `src/prevue/review.py` — `run_review()` orchestration; threshold filtering,
  budget allocation, inline posting, and check creation slot after
  `engine.review(req)`; config loading joins `load_ruleset()`.
- `src/prevue/github/comments.py` — `render_body()` restructures per D-26
  (Verdict/table/details); `upsert_sticky()`/`upsert_skip_note()` unchanged
  upsert mechanics.
- `src/prevue/github/client.py` — `get_authenticated_pull()` / `PrContext`;
  check-run creation needs the repo object + head SHA from here.
- `src/prevue/classify/rules.py` — `load_ruleset()` / merge pattern the new
  `review:` config section follows (additive, trusted base ref).

No external ADRs — greenfield repo; decisions captured above + in REQUIREMENTS.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`Finding` / `ReviewResult` models** (`models.py`) — schema already exists;
  this phase adds parse-and-validate, not new contract design.
- **`_build_prompt()` + untrusted-data fencing** (`copilot_cli.py`) — JSON
  output instructions, rubric, and 4C bar append to the existing trusted
  instructions block; untrusted-diff fencing pattern stays as-is.
- **`EngineFailure` / red-run path** (`copilot_cli.py`, `cli.py`) — hard
  failures already exit 1; parse failure must NOT route through this.
- **Sticky Metadata audit section** (`comments.py`) — extend with dropped-
  finding count, degrade notice, thresholds in effect.
- **`load_ruleset()` config merging** (`classify/rules.py`) — the `review:`
  section reuses this prevue.yml loading/validation path.
- **`run_review()` seam** (`review.py`) — single orchestration point; the new
  post-engine stage (validate → threshold → budget → place → check) slots
  after `engine.review(req)`.

### Established Patterns
- pydantic at every system boundary — finding validation (D-03) and review
  config (D-16) follow.
- Fail-closed for framework/consumer bugs (Phase 1 D-09, Phase 3 D-12) vs
  graceful degrade for engine output quality (new in this phase, ENGN-03) —
  keep the two classes visibly distinct in code paths.
- Deterministic + auditable: Python owns all GitHub writes and markdown
  rendering (Phase 1 sticky pattern → now inline comments + check too).
- Compact Metadata audit trail accretes per phase (labels → bundles → skills →
  now findings accounting).

### Integration Points
- `engine.review(req)` → **[new: extract/validate findings → retry-or-degrade
  → severity filter → budget rank → position-validate (unidiff) → split
  inline/summary]** → `create_review(COMMENT)` + restructured `upsert_sticky`
  + `create_check_run`.
- `ReviewRequest.diff.files[].patch` provides the hunks unidiff validates
  positions against — already on the request, no new fetch.
- Workflow YAML (`review.yml` and Phase 5 reusable workflow) needs
  `checks: write` added to the minimal permission set; document it.

</code_context>

<specifics>
## Specific Ideas

- **User requirement: every review comment follows 4C — Clarity, Conciseness,
  Correctness, Completeness — and all comments share one uniform template**
  (D-21/D-22). Template structure is deterministic Python rendering; 4C is
  prompt guidance. This came up unprompted — treat it as a hard requirement,
  not polish.
- **Trust is the through-line:** never false-block (parse → neutral, D-04),
  never flood (budget 10, D-18), never mislead (no line-snapping, D-17; no
  coercion, D-03), never hide (complete index, D-14/D-23). Every decision
  defends "a gate consumers can trust."
- The two failure classes (hard failure = red run vs parse failure = neutral
  degrade) must stay architecturally distinct — D-04 is the phase's defining
  behavior per ENGN-03.

</specifics>

<deferred>
## Deferred Ideas

- **GitHub one-click ```suggestion blocks** (→ v2, CUST-02): `Finding.suggestion`
  renders as a plain fenced code block in v1 (D-21).
- **Stale inline-comment handling on re-runs** (→ v2, LIFE-04): re-runs post a
  fresh review; auto-resolving outdated threads is lifecycle work.
- **Comment dedupe across runs** (→ v2, LIFE-02): no fingerprinting in v1.
- **Workflow-input config pass-through** (→ Phase 5, WKFL-03): thresholds live
  only in `prevue.yml` for now.
- **Token/cost transparency in summary** (→ Phase 6, OUTP-04): the findings
  table adds placement accounting but not token accounting.

None of the above is scope creep into Phase 4 — discussion stayed within the
structured-findings-and-gate boundary.

</deferred>

---

*Phase: 4-Structured Findings & Merge Gate*
*Context gathered: 2026-06-12*
