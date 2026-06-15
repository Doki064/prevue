# Phase 7: Customization & Hardening - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn Prevue from a working tool into a true **framework**: consumers extend and
override skills safely, prompt-injection defenses are *verified* (not assumed),
every review proves the token-efficiency thesis with transparent per-bundle
budgets, and oversized PRs are reviewed within a token budget with explicit
disclosure of what was skipped.

**Requirements:** SKIL-03, SECR-02, OUTP-04, DIFF-03.

**In scope:**
- Consumer custom/override skills under `.github/prevue/skills/` (per-file merge,
  `skills.exclude`, size/count caps) — read from the trusted base ref (SKIL-04)
- Prompt-injection: red-team all untrusted vectors, add defense-in-depth
  hardening, ship adversarial CI tests + a SECURITY.md threat model
- Token transparency in the sticky summary: tokens used (hybrid actual/estimate,
  review + classify split) and per-bundle skills-loaded-vs-skipped ratios
- Large-PR handling: skill/risk-weighted file packing within a token budget that
  reserves output tokens, with a "N files not reviewed" disclosure
- Consumer-facing docs (skill authoring, override/exclude, budget knobs, security)

**Out of scope:**
- Incremental / lifecycle review (review only newest diff since last-reviewed SHA;
  dedupe commits that address prior findings) → v2 LIFE-01/02/03/04, own phase
- Functional Gemini adapter (stays a registered skeleton)
- GitHub App installation-token auth (PAT / named secrets only in v1)
- Per-engine timeout/budget tuning (deferred pending latency data)

</domain>

<decisions>
## Implementation Decisions

### Consumer Skill Override & Customization (SKIL-03)
- **D-01:** Consumer skills live at `.github/prevue/skills/<bundle>/<skill>.md`,
  loaded from the **trusted base-ref checkout** (P6 D-04 already checks out the
  consumer repo at `base.sha`; SKIL-04 — never PR head). The loader today reads
  only the packaged `prevue.skills` tree (`loader.py:_skills_root()`); add a
  second consumer source and merge.
- **D-02:** **Per-file merge keyed on `bundle/filename`.** A consumer file at the
  same `bundle/filename` as a built-in **overrides** that one skill; a *new*
  filename in a bundle **adds alongside** built-ins. Precedence falls out as
  consumer-override > consumer-custom > built-in (matches ROUT-01). **Not**
  whole-bundle replace — the user explicitly wants to add to e.g. `security/`
  alongside the built-ins.
- **D-03:** **Selection mechanism unchanged** — consumer skills are selected by
  their own `applies-to` globs against changed paths, exactly like built-ins
  (`loader.select_skills`). **No classification label or prevue.yml routing entry
  is needed** — the glob is the trigger. `bundle` = directory name (drives
  ordering/display via `canonical_index`). New (non-canonical) consumer bundle
  names append **after** the canonical five in display/order.
- **D-04:** **Malformed consumer skill → fail-closed (red check).** Bad/missing
  frontmatter or invalid `applies-to` fails the review until the consumer fixes
  or excludes it. Consistent with the fail-closed config posture (distinct from
  graceful classification-degrade). `skills/models.py` already fail-closed
  validates frontmatter — extend to consumer-sourced files.
- **D-05:** **`skills.exclude` list in `.github/prevue.yml`**, addressed by
  `bundle/filename` (same scheme as the override key). Removes the skill at that
  path from the final set **regardless of source** — disables a built-in OR
  silences a skill. Add to `PrevueConfig` (`config.py`, `extra="forbid"` style).
- **D-06:** **Revert-to-built-in = delete the override file.** The built-in is
  the automatic fallback layer, so removing the consumer file restores it and
  clears the red. `exclude` is **not** a revert mechanism (it kills the path
  entirely, built-in included); deleting the file is the git-native fix. This is
  the resolution to the "malformed override, want built-in back" edge case.
- **D-07:** **Consumer-skill guardrails** — cap per-skill bytes and total
  consumer-skill bytes/count. An over-cap skill is **skipped + disclosed** in the
  summary (a resource concern, not a correctness error → skip, not fail). Stops
  an oversized consumer skill from crowding out the diff/output budget.

### Prompt-Injection Verification & Hardening (SECR-02)
- **D-08:** **Red-team all four untrusted vectors:** (1) diff hunk content,
  (2) filenames/paths, (3) the P6 `classify()` fallback prompt (unmatched paths),
  (4) engine tool access to PR fields — audit each adapter's `--allow-tool` set
  for any tool that could fetch PR title/body/comments at runtime, re-introducing
  text deliberately excluded from `DiffBundle`.
- **D-09:** The current baseline is sound and stays the design: `DiffBundle`
  deliberately excludes PR title/body (`models.py`); `prompt.py` fences
  diff/files inside `~~~UNTRUSTED DATA` blocks (4-backtick diff fences) and
  json-escapes paths. Phase 7 **proves** it holds and hardens it.
- **D-10:** **Posture = verify + add hardening.** Hardening candidates (final set
  decided in research/planning): instruction-reassertion after untrusted blocks;
  audit/tighten each engine's `--allow-tool` set (deny PR-metadata/network
  reach); ensure `classify()` reuses the same fencing; lean on the existing P4
  finding-position validation (`positions.py` — invalid positions already drop to
  the summary) as the output-side guard that findings reference only real changed
  lines.
- **D-11:** **Trust boundary documented:** consumer skill content = **trusted**
  instructions (the consumer owns their base-ref repo); **untrusted** = PR
  diff / paths / metadata. State this boundary explicitly in the threat doc.
- **D-12:** **Artifacts:** automated adversarial test fixtures in the suite (CI
  regression guard — injection attempts must NOT alter verdict/findings/labels)
  **plus** a `SECURITY.md` threat-model section documenting each vector and its
  mitigation.

### Token Transparency (OUTP-04)
- **D-13:** **Token counts = hybrid actual-else-estimate.** Use engine-reported
  usage when the CLI emits it; otherwise estimate from prompt+response size and
  mark it `~est`. Honest across adapters that don't report usage. `engine_meta`
  (`flow.py`) carries only `model` + `duration_s` today — extend it.
- **D-14:** **Breakdown = split review + classify.** Show review tokens and, when
  the P6 LLM fallback fired, classify tokens separately — the real
  hybrid-classification cost story.
- **D-15:** **Skills loaded vs skipped = per-bundle compact ratios**, e.g.
  `Skills: 3/13 loaded — security 2/3 · frontend 1/4 · backend 0/3 · data 0/2 ·
  infra 0/1`. Loaded skill names stay listed as today (`comments.py:render_body`).
- **D-16:** **Transparency is computed on the PACKED (reviewed) set, not the full
  changed set** (see D-19). The summary MUST explicitly state that
  classification/skills reflect **only the reviewed files** and that **N files
  were dropped** — coupling the OUTP-04 line to the DIFF-03 disclosure so a
  partial review never over-reports coverage.

### Large-PR Token Budget & Packing (DIFF-03)
- **D-17:** **File-granular packing** — pack whole file diffs in priority order
  until the budget is hit; the remainder are "not reviewed." **No mid-file
  truncation** (would mislead the review). `diff.py:fetch_diff()` grabs everything
  today; add a budget/packing step.
- **D-18:** **Priority = skill/risk-weighted.** Files that matched a loaded skill
  go first, ordered by bundle priority (security highest); remaining budget fills
  with lower-signal files. Maximizes review value per token.
- **D-19:** **Skill selection + transparency run on the PACKED set only** (token
  optimization) — files dropped by budget do NOT drive skill loading or the
  per-bundle ratios, and do NOT incur a `classify()` fallback call. Paired with
  the explicit disclosure (D-16). Sequencing principle: free glob-classification
  may seed packing priority across all files, but the **paid LLM fallback only
  touches files that will actually be reviewed.** Exact classify↔pack ordering =
  planner.
- **D-20:** **Budget = `review.max_input_tokens` config knob** (sensible default)
  **+ a configurable output reserve** so packed input can't starve the response
  (REQUIREMENTS DIFF-03 note).
- **D-21:** **Disclosure = count + collapsible list.** A prominent
  `N files not reviewed (over token budget)` line plus a collapsible `<details>`
  listing the skipped paths and the ordering reason.
- **D-22:** **Classify-fallback is already batched** — P6 shipped
  `CLASSIFY_BATCH_SIZE = 100` (`llm_fallback.py`): one `adapter.classify()` call
  per 100 unmatched paths, **not per-file**. Keep batched; scope to the packed
  set (D-19) to bound huge-PR classification cost.
- **D-23:** **Partial coverage → no green PASS.** A clean-but-partial review
  (files dropped) degrades to **NEUTRAL**, never green PASS, so it never falsely
  blesses unreviewed code; findings still **FAIL** as normal (error-severity →
  fail). A false green is the worst outcome for a security gate.
- **D-24:** **No-file-fits edge** (a single file's diff exceeds the whole input
  budget): **skip + neutral disclosure** — review nothing, post a neutral check +
  "PR too large to review within budget." Fail-safe, never crashes, consistent
  with the no-truncation rule. Reuse P6 `conclude_skip_check` / skip-note path.

### Framework Documentation
- **D-25:** **Consumer-facing docs are a Phase 7 deliverable** — a `docs/` section
  (or README) covering skill authoring, override/exclude, budget knobs, and the
  security posture. Pairs with `SECURITY.md` (D-12). This is what makes Prevue
  "behave as a framework."

### Claude's Discretion
- Exact `.github/prevue.yml` field names (`skills.exclude`, skill-cap knobs,
  `review.max_input_tokens`, the output-reserve knob) — keep obvious + documented;
  match the P6 `extra="forbid"` section style.
- The token-estimate heuristic constant (bytes-per-token ratio) and where the
  estimator lives.
- The final hardening set within D-10.
- The non-canonical bundle display/ordering rule (D-03).
- Exact consumer-skill cap values, per-skill and total (D-07).
- The classify↔pack sequencing implementation (D-19).
- Skipped-file tie-breaking within the skill/risk priority (D-18).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` §Phase 7 — goal, the 4 success criteria, requirement
  list (SKIL-03, SECR-02, OUTP-04, DIFF-03).
- `.planning/REQUIREMENTS.md` — SKIL-03, SECR-02, OUTP-04, DIFF-03 definitions;
  the DIFF-03 output-reserve note; ROUT-01 precedence chain (consumer override >
  consumer custom > built-in); SKIL-04 base-ref-only loading; and the deferred
  v2 LIFE-01/02/03/04 (Review Lifecycle) this phase explicitly does NOT cover.
- `.planning/phases/06-reusable-workflow-hybrid-classification/06-CONTEXT.md` —
  P6 D-04 (consumer checkout at `base.sha`), D-09 (batched per-unmatched-path
  fallback), D-11 (`classify()` capability on the adapter ABC), D-12 (graceful
  classification degrade), and the `.github/prevue.yml` config-precedence surface.

### Code to wire / extend
- `src/prevue/skills/loader.py` — `_skills_root()` (packaged-only today),
  `load_skills()`, `select_skills()`, `assemble_instructions()`; add the consumer
  source + per-file merge (D-01/02/03).
- `src/prevue/skills/models.py` — `Skill` pydantic model (fail-closed frontmatter
  validation); extend to validate consumer-sourced skills (D-04).
- `src/prevue/config.py` — `PrevueConfig` + section models (`extra="forbid"`); add
  `skills.exclude`, skill caps, `review.max_input_tokens` + output reserve
  (D-05/07/20).
- `src/prevue/engines/prompt.py` — `_safe_diff_block`, `_escape_line`,
  `_build_prompt`, the `UNTRUSTED DATA` fencing, `OUTPUT_CONTRACT`; injection
  hardening + classify-prompt fencing (D-08/10).
- `src/prevue/engines/base.py` + adapters (`copilot_cli.py`, `claude_code_cli.py`,
  `cursor_cli.py`, `gemini_cli.py`) — `--allow-tool` sets to audit (D-08); the
  `classify()` + `review()` invocations; token-usage extraction for `engine_meta`
  (D-13).
- `src/prevue/engines/flow.py` — `engine_meta` population (model, duration_s
  today); add token counts (D-13/14).
- `src/prevue/classify/llm_fallback.py` — `CLASSIFY_BATCH_SIZE=100` batching
  (already bounded); scope the fallback to the packed set (D-19/22).
- `src/prevue/github/diff.py` — `fetch_diff()`; add the budget/packing step
  (D-17/18/20).
- `src/prevue/github/comments.py` — `render_body()` metadata (`Skills:`/`Bundles:`
  lines); per-bundle ratios + token line + skipped-files disclosure
  (D-15/16/21).
- `src/prevue/github/checks.py` — verdict/check conclusion; partial → neutral and
  no-fit → neutral (D-23/24); reuse the P6 `conclude_skip_check` / skip-note path.
- `src/prevue/github/positions.py` — existing position validation, used as the
  output-side injection guard (D-10).
- `src/prevue/review.py` — `run_review` orchestration; wires classification →
  packing → skill selection → review → output; integration point for
  D-16/19/23.

### Stack facts
- `.planning/research/STACK.md` — reusable-workflow permissions/secrets boundary,
  LLM-fallback-through-adapter pattern, pins.
- `CLAUDE.md` §Technology Stack / §What NOT to Use — pathspec gitignore-glob
  semantics, python-frontmatter, no `secrets: inherit`, no `pull_request_target`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `loader.select_skills(skills, paths)` (`skills/loader.py`): glob-based selection
  already does exactly what consumer skills need — they participate with zero new
  selection logic once loaded (D-03).
- `Skill` model fail-closed validation (`skills/models.py`): the malformed-skill
  posture (D-04) reuses the existing frontmatter validation.
- `upsert_skip_note` + `conclude_skip_check` (P6, `github/comments.py` /
  `github/checks.py`): the neutral-skip path is directly reusable for the no-fit
  edge (D-24).
- `positions.py` position validation (P4): doubles as the output-side injection
  guard (findings can only reference real changed lines) (D-10).
- `llm_fallback._chunk_paths` + `CLASSIFY_BATCH_SIZE` (P6): batching is already
  in place — no per-file calls to remove (D-22).
- `engine_meta` dict on `ReviewResult` (`models.py`, populated in `flow.py`): the
  carrier for token counts (D-13/14).

### Established Patterns
- Fail-closed for config/skill errors vs graceful degrade for classification
  (P5/P6) — D-04 (fail) vs D-07 over-cap (skip) follow this split.
- Trusted-base-ref-only reads (SECR-01/SKIL-04): consumer skills and prevue.yml
  come from `base.sha`, never PR head — the SECR-02 trust boundary (D-11).
- `extra="forbid"` pydantic config sections (`config.py`): new knobs follow the
  same shape (D-05/07/20).
- Untrusted-data fencing + json-escaping in `prompt.py`: classify prompt and any
  new prompt assembly reuse it (D-08/10).

### Integration Points
- `review.py:run_review` — insert the packing step between classification and
  review; route packed-set paths into skill selection (D-16/19).
- `diff.py:fetch_diff` — where the token budget / file packing lands (D-17/18/20).
- `comments.py:render_body` — token line, per-bundle ratios, skipped-files
  disclosure (D-15/16/21).
- `checks.py` — partial-coverage and no-fit neutral verdicts (D-23/24).
- Each engine adapter's `--allow-tool` set + token-usage parsing (D-08/13).

</code_context>

<specifics>
## Specific Ideas

- The per-bundle transparency line should read like
  `Skills: 3/13 loaded — security 2/3 · frontend 1/4 · backend 0/3 …` (user gave
  this exact compact shape — D-15).
- **A partial review must never show green** — for a security gate, a false green
  is the worst outcome (D-23). User emphasized this directly.
- User flagged per-file LLM classify calls as unacceptable; confirmed P6 already
  batches at 100/call — keep batched + scope to the packed set (D-22).
- Override revert is "delete the file," not an exclude flag — driven by the user's
  malformed-override edge case (D-06).
- Consumer wants to *add* skills to an existing built-in domain (e.g. `security/`)
  alongside the built-ins, which is why merge is per-file, not bundle-replace
  (D-02).

</specifics>

<deferred>
## Deferred Ideas

- **Incremental / lifecycle review** (user-raised this session): review only the
  newest diff since the last-reviewed SHA, and dedupe/skip commits that merely
  address prior review findings — instead of re-classifying and re-reviewing the
  whole PR on every push. Maps to existing **v2 requirements**: LIFE-01
  (incremental since last SHA, sticky-marker state), LIFE-02 (comment dedupe),
  LIFE-04 (auto-resolve outdated inline threads). Needs *persistent cross-run
  state* — a different axis from Phase 7's customization/hardening scope.
  **Recommendation:** its own phase under a new **v2 "Review Lifecycle"
  milestone** after v1 (Phase 7) ships. Promote via `/gsd-new-milestone` →
  `/gsd-phase`, or `/gsd-review-backlog`.
- **Functional Gemini adapter** — stays a registered skeleton (carried from P6).
- **GitHub App installation-token auth** — PAT / named secrets only in v1
  (carried from P6).
- **Per-engine timeout/budget tuning** — deferred pending latency data
  (carried from P5/P6).

</deferred>

---

*Phase: 7-Customization & Hardening*
*Context gathered: 2026-06-14*
