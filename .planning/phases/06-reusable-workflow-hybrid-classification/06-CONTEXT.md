# Phase 6: Reusable Workflow & Hybrid Classification - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the first externally shippable surface: package Prevue as a consumable
GitHub **`workflow_call`** reusable workflow. Any repo adopts it with a minimal
caller snippet; the workflow self-checkouts both repos at trusted refs, reads
consumer config, runs the full pipeline under minimal permissions, falls back to
a cheap LLM classification call for ambiguous files, and skips drafts / bots /
filtered PRs by default.

**Requirements:** WKFL-01, WKFL-02, WKFL-03, WKFL-04, CLSF-02, NOIS-01.

**In scope:**
- A `workflow_call` reusable workflow + a thin local `pull_request` caller that
  dogfoods it on this repo
- Self-checkout of the Prevue repo (pinned to its own release) and the consumer
  repo (base ref only) — diff still API-fetched, no PR-head checkout
- Consumer config surface: minimal `workflow_call` inputs (engine, config-path) +
  a unified `.github/prevue.yml` (read from the trusted base ref) with named
  sections; precedence input > prevue.yml > built-in
- Wire `load_ruleset(consumer_path)` and the gate config to the SAME
  `.github/prevue.yml` (closes the `review.py:45/46` gap)
- Hybrid classification: per-file LLM fallback for files no glob rule matched,
  via a new `classify()` capability on the engine adapter, reusing the selected
  engine + a cheap model; degrade-to-`general` + explicit disclosure on failure
- Default skip conditions (drafts, bot authors, skip-label) with config overrides
- Minimal, documented token scopes for the workflow

**Out of scope (Phase 7+):**
- Consumer custom skill bundles / overrides (SKIL-03)
- Prompt-injection red-team verification (SECR-02)
- Token transparency reporting (OUTP-04)
- Large-PR token budget / file packing (DIFF-03)
- Functional Gemini adapter (stays a skeleton)
- GitHub App installation-token auth flow (PAT/secrets only in v1)

</domain>

<decisions>
## Implementation Decisions

### Reusable Workflow Contract (WKFL-01/02/04)
- **D-01:** Ship a **reusable workflow + thin caller** pair. New
  `prevue-review.yml` with `on: workflow_call` is the shippable interface; the
  existing `review.yml` becomes a thin `pull_request` caller that
  `uses: ./.github/workflows/prevue-review.yml` so this repo dogfoods the exact
  path consumers hit.
- **D-02:** Credentials pass via **named per-engine secrets**, declared in the
  reusable workflow's `secrets:` block as not-required. Consumer passes only the
  secret for their chosen engine (`copilot-github-token` / `anthropic-api-key` /
  `cursor-api-key` → mapped to the Phase 5 native env vars). No `secrets: inherit`
  (CLAUDE.md constraint). Fail-closed if the selected engine's secret is absent
  (Phase 5 D-06).
- **D-03:** The reusable workflow checks out the **Prevue code at its own
  matching release tag** (workflow at `vX` → `actions/checkout` of
  `Doki064/prevue@vX`), hardcoded for self-consistency, with an optional input
  override for testing. Avoids fragile `github.workflow_ref` parsing. (In
  `workflow_call`, only the YAML loads at the pinned ref — the Python package
  must be explicitly checked out.)
- **D-04:** Check out the **consumer repo at `pull_request.base.sha`** (trusted),
  `persist-credentials: false`. Used to read `.github/prevue.yml` and (future)
  consumer skills. The diff itself stays API-fetched; PR-head code is **never**
  checked out for analysis (preserves SECR-01).

### Consumer Config (WKFL-03)
- **D-05:** Config precedence is **workflow input > `.github/prevue.yml` >
  built-in default**. Per-call input overrides the committed repo baseline.
- **D-06:** **Minimal `workflow_call` inputs:** `engine` and `config-path`
  (+ optional `prevue-ref`). All behavioral config — classification rules,
  `review:` thresholds, `engine:`, `skip:`, classification fallback — lives in
  `.github/prevue.yml`. Keeps the caller snippet tiny and policy versioned.
- **D-07:** `prevue.yml` is read from **`.github/prevue.yml`** off the trusted
  base-ref checkout (D-04). `config-path` input overrides the location. Replaces
  the current cwd `prevue.yml` read (`review.py:46`).
- **D-08:** **Single unified `.github/prevue.yml`** with named top-level
  sections: classification rules (`ignore`/`labels`/`routing`), `review:` (gate
  thresholds), `engine:`, `skip:`, and `classification.fallback:`. Read once,
  feeds all consumers. **Wire `load_ruleset(consumer_path)`** so consumer
  classification rules actually apply (closes the `review.py:45` gap where no
  consumer_path is passed today).

### Hybrid Classification — LLM Fallback (CLSF-02)
- **D-09:** **Per-file trigger.** The LLM fallback fires only for files where
  **no glob rule matched**; sends just those paths (not the full diff) to a cheap
  model. The rule-match boolean IS the signal — no confidence score/threshold
  (no calibration data exists yet; confidence would be per-file with an
  uncalibrated knob). Files that match any rule stay **zero-token**; cost scales
  with ambiguity.
- **D-10:** **Reuse the selected engine adapter** (same `PREVUE_ENGINE`) with a
  **cheap/fast classification model** (separate model knob from the review
  model). Zero new dependencies, vendor-neutral, single auth path (STACK.md
  guidance: route fallback through the existing adapter).
- **D-11:** Add a **`classify()`/`complete()` capability method to the
  `EngineAdapter` ABC** — a label-only call each adapter implements via its own
  subprocess spawn. `review()` stays FINAL/untouched; this is a **documented
  capability extension, not a contract break**. Phase 5 hoisted the prompt to
  shared but NOT the per-engine subprocess spawn, which this needs. LLM output
  is constrained to the canonical label set and validated.
- **D-12:** **On fallback failure** (error / timeout / unparseable): **degrade to
  the `general` label and continue the review** (baseline review, no crash, no
  red X), AND **disclose it explicitly** in the sticky summary (e.g.
  "classification fallback unavailable — reviewed as `general`"). Distinct from
  engine-review failure, which is fail-closed/red (D-09 posture). Classification
  is a best-effort enhancement, not a gate.

### Skip Conditions (NOIS-01)
- **D-13:** **Hybrid evaluation.** Draft skip via workflow-level
  `if: !github.event.pull_request.draft` — free, no runner spin, and drafts can't
  merge so no check is needed. Bot + skip-label/title skips run **in Python**
  after reading `.github/prevue.yml` (they need config AND must post a neutral
  skip check so required-check branch protection isn't left pending).
- **D-14:** **Bot detection** = GitHub author **user type == `Bot`** (covers
  dependabot/renovate/any App generically). A `skip.review_bots: [<login>...]`
  list re-includes specific bots the consumer DOES want reviewed. **Skip ≠
  auto-merge:** skipping only means "no AI review + neutral check"; Prevue never
  merges. The neutral check is non-blocking so a consumer's own auto-merge isn't
  obstructed.
- **D-15:** **Default title/label filter:** a **`skip-review` label** skips the
  PR out of the box (satisfies NOIS-01 "by default"). `prevue.yml` `skip:`
  exposes `skip_labels` and `skip_title_patterns` lists to extend/replace.
- **D-16:** **Skip surfacing** reuses the existing `upsert_skip_note` +
  `conclude_skip_check` path (built for empty PRs): post a **neutral check + a
  short sticky note stating the reason** (e.g. "skipped: bot author
  dependabot[bot]"). Neutral keeps required checks from blocking.

### Claude's Discretion
- Exact `prevue.yml` field names within each section (e.g.
  `skip.bots` / `skip.review_bots` / `classification.fallback.model`) — lock
  during planning; keep them obvious and documented.
- Exact reusable-workflow input names and the release-tag checkout mechanism.
- Whether the cheap classification model is a fixed per-engine default or a
  `classification.fallback.model` config knob (lean toward the config knob with a
  sensible default).
- Module placement for the LLM-fallback classification logic (e.g.
  `classify/llm_fallback.py`) and the `classify()` signature shape.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` §Phase 6 — goal, success criteria, requirement list.
- `.planning/REQUIREMENTS.md` — WKFL-01/02/03/04, CLSF-02, NOIS-01 definitions.
- `.planning/phases/05-multi-engine-adapter-support/05-CONTEXT.md` — Phase 5
  D-03 (PREVUE_ENGINE env+registry, Phase 6 wires prevue.yml to same), D-04/D-09
  (fail-closed), and the explicit deferrals to Phase 6 (rich prevue.yml engine
  config, per-engine tuning).

### Workflow & packaging
- `.github/workflows/review.yml` — current `pull_request` wrapper; becomes the
  thin caller (D-01).
- `.github/workflows/ci.yml` — existing CI (zizmor/actionlint posture to mirror).
- `CLAUDE.md` §Technology Stack / §What NOT to Use — `workflow_call` vs composite
  rationale, no `secrets: inherit`, no `pull_request_target`, named-secret
  pass-through, install patterns (curl-installs, uv sync --locked).

### Code to wire / extend
- `src/prevue/review.py` §`run_review` — orchestration; **line ~45**
  `load_ruleset()` (no consumer_path — wire D-08) and **line ~46**
  `PREVUE_CONFIG_PATH`/`prevue.yml` cwd read (repoint to `.github/prevue.yml`,
  D-07). Where skip checks (D-13) and the LLM fallback (D-09) hook in.
- `src/prevue/classify/classifier.py` — the `general`-when-no-rule path
  (`labels = {GENERAL_LABEL: ...}`, lines ~40-41) is where per-file LLM fallback
  (D-09) integrates.
- `src/prevue/classify/rules.py` — `load_ruleset(consumer_path)` + `merge_rules`
  (consumer additive/override merge already implemented; just not invoked).
- `src/prevue/gate.py` — `ReviewConfig` + `load_review_config(consumer_path)`
  (the `review:` section reader; unify with D-08 single-file read).
- `src/prevue/engines/base.py` — the `EngineAdapter` ABC; add the `classify()`
  capability (D-11) WITHOUT touching `review()`.
- `src/prevue/engines/registry.py` — `PREVUE_ENGINE` → adapter (Phase 5);
  fallback reuses the selected adapter (D-10).
- `src/prevue/engines/prompt.py` — shared prompt/fencing (Phase 5 hoist); the
  classification prompt reuses the same injection-safe fencing.
- `src/prevue/github/comments.py` (`upsert_skip_note`) +
  `src/prevue/github/checks.py` (`conclude_skip_check`) — reused for skip
  surfacing (D-16).

### Stack facts
- `.planning/research/STACK.md` — `workflow_call` vs composite action, reusable
  workflow permissions/secrets boundary, LLM-fallback-through-adapter pattern,
  setup-uv/Copilot/curl-install pins.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `merge_rules` / `load_ruleset(consumer_path)` (`classify/rules.py`): consumer
  config merge already built and tested — Phase 6 just has to *invoke* it from
  `run_review` with the resolved `.github/prevue.yml` path.
- `load_review_config(consumer_path)` + `ReviewConfig` (`gate.py`): consumer
  threshold reader already exists; unify under the single-file read (D-08).
- `upsert_skip_note` + `conclude_skip_check`: the empty-PR neutral-skip path is
  directly reusable for NOIS-01 skips (D-16) — add a reason string.
- `get_adapter(PREVUE_ENGINE)` + registry (Phase 5): the LLM fallback reuses the
  already-selected adapter (D-10) rather than instantiating its own.
- Shared `engines/prompt.py` fencing: the classification prompt reuses it for
  injection-safe assembly.

### Established Patterns
- Engine selection = `PREVUE_ENGINE` env → registry (Phase 5 D-03); Phase 6 adds
  the `engine:` prevue.yml section feeding the same env/registry, no interface
  change.
- Fail-closed for config/engine errors (Phase 5 D-04/D-09); but classification
  fallback degrades gracefully (D-12) — different failure class.
- Adapter = class with `subprocess`-based invocation, no wrapper libs; the
  `classify()` capability (D-11) follows the same shape.
- Trusted-base-ref-only reads (SECR-01): prevue.yml and skills come from
  base.sha, never PR head.

### Integration Points
- `review.py` line ~45/46: repoint config reads to `.github/prevue.yml` and wire
  `load_ruleset(consumer_path)`.
- `classifier.py` `general` path: per-file LLM fallback hook.
- `EngineAdapter` ABC: new `classify()` method (all four adapters implement;
  Gemini skeleton may `NotImplementedError`).
- Workflow `if:` (draft skip) + Python skip evaluation + neutral-skip surfacing.

</code_context>

<specifics>
## Specific Ideas

- Dogfood the exact consumer path: this repo's `review.yml` should `uses:` the
  reusable `prevue-review.yml` rather than duplicating the job body (D-01).
- User wants the bot-skip semantics crystal clear in docs: **skip ≠ auto-merge.**
  Prevue only declines to review + posts a non-blocking neutral check; merging is
  always the consumer's branch-protection/auto-merge decision (D-14).
- Per-file fallback should keep the token story honest — only unmatched file
  paths enter the cheap-model prompt; any rule match keeps the PR zero-token.

</specifics>

<deferred>
## Deferred Ideas

- **Consumer custom skills / overrides** (SKIL-03) — Phase 7.
- **Prompt-injection red-team verification** (SECR-02) — Phase 7. (Phase 6 still
  reuses the existing fencing for the new classification prompt.)
- **Token transparency reporting** (OUTP-04) — Phase 7.
- **Large-PR token budget / prioritized file packing** (DIFF-03) — Phase 7.
- **Functional Gemini adapter** — stays a registered skeleton.
- **GitHub App installation-token auth** — PAT/named-secrets only in v1.
- **Per-engine timeout/budget tuning** — deferred from Phase 5; revisit when
  latency data exists.

</deferred>

---

*Phase: 6-Reusable Workflow & Hybrid Classification*
*Context gathered: 2026-06-13*
