# Phase 1: Walking Skeleton Review Loop - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

End-to-end PR review loop on a real Actions runner: a PR event triggers a run that fetches the diff and changed-file metadata via the GitHub API (no untrusted checkout), the Copilot CLI adapter produces a review through the pluggable `EngineAdapter` interface, and a sticky summary comment is posted/updated in place on the PR. Trigger model is `pull_request` only; fork PRs documented as unsupported. Requirements: DIFF-01, ENGN-01, ENGN-02, OUTP-01, SECR-01.

Classification, routing, skill loading, inline comments, checks/merge gate, and consumer packaging are explicitly later phases.

</domain>

<decisions>
## Implementation Decisions

### Engine output shape
- **D-01:** Phase 1 adapter output is a freeform markdown review (prose). Structured-findings prompt engineering and schema validation are deferred to Phase 4.
- **D-02:** The `EngineAdapter` interface is locked to its final ENGN-01 shape now: pydantic `ReviewRequest` → `ReviewResult` with a findings list. The skeleton leaves findings empty/unvalidated and carries the prose review in the result — the adapter API must not break in Phase 4.
- **D-03:** Model selection: use the Copilot CLI default model, with `COPILOT_MODEL` env passthrough as the configuration escape hatch. No pinned model in the adapter.

### Summary comment design
- **D-04:** Sticky comment is a sectioned shell from day one — fixed sections (Verdict / Review / Metadata) that later phases fill in. Empty placeholders are acceptable in v1.
- **D-05:** No verdict in Phase 1 — the Verdict section exists but states no verdict; verdicts appear when the merge gate exists (Phase 4). Avoid implying a gate that isn't enforced.
- **D-06:** On subsequent runs the sticky comment content is replaced in place entirely — one comment, always current (OUTP-01). No run history kept in the comment.

### Review prompt composition
- **D-07:** Prompt input is the diff + changed-file list only. PR title/body (attacker-writable text) are excluded from the prompt entirely in Phase 1 — cleanest prompt-injection posture from day one.
- **D-08:** Diff hunks only — no surrounding/full file content fetching in Phase 1. Context packing is a later concern (Phase 6 / v2).

### Failure visibility
- **D-09:** On engine failure (auth error, timeout, unusable output): the workflow run fails (non-zero exit, visible failed run, details in logs); the sticky comment is left untouched. No error comments on the PR thread.
- **D-10:** Copilot CLI review call timeout: ~5 minutes, then fail.

### E2E verification setup
- **D-11:** Both verification paths: a wrapper workflow inside the prevue repo for fast iteration, plus a separate sandbox repo with seeded test PRs calling Prevue at a ref for the real consumer-path proof. (STACK.md flags act as unreliable for `workflow_call` — live runs are the real verification.)
- **D-12:** Execution starts with a tiny throwaway spike workflow (just run `copilot -p` on a clean runner; observe auth, output stability, timing) before building the pipeline. Spike findings feed the adapter design — this de-risks the phase's biggest unknown (flagged in STATE.md).
- **D-13:** User has Copilot access and will create the `COPILOT_GITHUB_TOKEN` PAT as a repo secret — not a blocker.

### Claude's Discretion
- Baseline review instructions (the prompt's system-style preamble): Claude drafts generic high-quality review instructions during planning. Skills replace most of this in Phase 3.
- Sticky-comment marker mechanism, repo layout, CLI invocation details, and other technical implementation choices.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Stack & platform facts
- `.planning/research/STACK.md` — verified versions and packaging facts: Copilot CLI 1.0.x headless invocation (`copilot -p ... --no-ask-user`, `COPILOT_GITHUB_TOKEN`), PyGithub 2.9.1, pydantic 2.13.4, uv/setup-uv, act `workflow_call` limitations
- `.planning/PROJECT.md` — pipeline definition, constraints (minimal token scopes, `pull_request` trigger only), key decisions
- `.planning/REQUIREMENTS.md` — DIFF-01, ENGN-01, ENGN-02, OUTP-01, SECR-01 definitions and out-of-scope table

No other external specs/ADRs exist — greenfield repository.

</canonical_refs>

<code_context>
## Existing Code Insights

Greenfield repository — no application code exists yet (LICENSE, `.planning/`, and agent skill files only). No codebase maps in `.planning/codebase/`.

### Integration Points
- New code establishes the patterns: Python package managed by uv, pydantic models for the adapter contract, workflow YAML under `.github/workflows/`.

</code_context>

<specifics>
## Specific Ideas

- The adapter contract should follow the STACK.md pattern: pydantic model pair (`ReviewRequest` → `ReviewResult` with findings list), each adapter a class implementing one `review()` method that shells out via stdlib `subprocess`.
- Security posture is part of the skeleton's identity: no untrusted checkout, `pull_request` trigger only, no PR title/body in prompts.

</specifics>

<deferred>
## Deferred Ideas

Raised during discussion; none belong in Phase 1:

- **LLM classification call context** (→ Phase 5, CLSF-02): compose the cheap fallback-classification prompt from diff hunks + PR summary/description/keywords for optimal context. PR description is untrusted text — must be passed as clearly-delimited quoted *data*, never instructions (interacts with SECR-02).
- **Logical review splitting** (→ v2, CUST-04): splitting oversized reviews into multiple calls must chunk logically so cross-references stay together (no "function in chunk A refers to function in chunk B" blindness). v1 Phase 6 (DIFF-03) only does prioritize-and-truncate packing with disclosure.
- **Output-token reservation** (→ Phase 6, DIFF-03): when input/output share a token pool, the budget must reserve tokens for output so a packed input can't starve the review response. Recorded as a requirement note under DIFF-03.
- **Committed-secret alerting** (→ Phase 3, SKIL-02): the built-in security skill bundle must instruct the review to flag secrets/credentials committed in the diff (alert, not redact — repos should contain no secrets). Recorded as a requirement note under SKIL-02.

</deferred>

---

*Phase: 1-Walking Skeleton Review Loop*
*Context gathered: 2026-06-11*
