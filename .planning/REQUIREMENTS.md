# Requirements: Prevue

**Defined:** 2026-06-12
**Core Value:** Optimal memory context and token usage when integrating with AI — load only the review skills the PR actually needs — while keeping review quality on par with a full-context review.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Workflow Packaging

- [x] **WKFL-01**: Consumer can call Prevue as a GitHub reusable workflow (`workflow_call`) from any repo with a minimal caller snippet
- [x] **WKFL-02**: Reusable workflow self-checkouts the Prevue repo (pinned ref) and the consumer repo, then runs the pipeline via a single CLI invocation
- [x] **WKFL-03**: Consumer can configure run behavior via workflow inputs and a `.github/prevue.yml` config file read from the trusted base ref
- [x] **WKFL-04**: Workflow runs with minimal token scopes (read contents, write PR comments/checks) and documents required permissions

### Diff Fetching

- [x] **DIFF-01**: Pipeline fetches the PR diff and changed-file metadata via the GitHub API on PR events (no checkout of untrusted code required for diff analysis)
- [x] **DIFF-02**: Pipeline applies default path filters (lockfiles, generated, vendored, binaries) and consumer-defined ignore globs before classification
- [x] **DIFF-03**: Pipeline enforces a token budget with prioritized file packing and explicitly discloses "N files not reviewed" in the summary
  - *Note (added 2026-06-11, Phase 1 discussion):* when input and output share a token pool, the budget must reserve tokens for the review output so packed input cannot starve the response

### Classification

- [x] **CLSF-01**: Deterministic classifier assigns category labels (security, frontend, backend, data, infra) from file globs, paths, lockfiles, and extensions at zero token cost
- [x] **CLSF-02**: Ambiguous diffs fall back to a cheap/fast LLM classification call; clear-cut PRs spend no classification tokens
- [x] **CLSF-03**: Classification rules are data (configurable/overridable), and the resulting labels + matched rules are auditable in the review output

### Routing & Skills

- [x] **ROUT-01**: Router maps classification labels to skill bundles with precedence: consumer override > consumer custom > built-in
- [x] **SKIL-01**: Skill loader loads only the matched skill bundles into the review context (SKILL.md-style markdown bundles with routing metadata)
- [x] **SKIL-02**: Framework ships built-in skill bundles: security, frontend, backend, data, infra
  - *Note (added 2026-06-11, Phase 1 discussion):* the built-in security bundle must instruct the review to flag secrets/credentials committed in the diff (alert, not redact)
- [x] **SKIL-03**: Consumer repos can add custom skills and override built-in bundles via `.github/prevue/skills/`
- [x] **SKIL-04**: Skills are loaded from the trusted base ref only; PR-modified skill files are never executed in the same run

### Engine Adapter

- [x] **ENGN-01**: Engine adapters implement a pluggable interface: review context in → structured findings (file, line, severity, message, suggestion) out
- [x] **ENGN-02**: GitHub Copilot CLI adapter runs headless on Actions runners (`copilot -p ... -s --no-ask-user`, auth via `COPILOT_GITHUB_TOKEN`, minimal `--allow-tool` set)
- [x] **ENGN-03**: Engine output is schema-validated with retry-then-degrade handling; a parse failure produces a neutral check, never a crash or false block
- [x] **ENGN-04**: Additional engine adapters (Claude Code CLI, Cursor CLI, Gemini CLI) implement the same pluggable interface and are selectable via config, validating the engine abstraction beyond Copilot (promoted from CUST-03, 2026-06-13)
- [x] **ENGN-05**: Pipeline supports configurable multi-call review (max_review_calls, default 1 = single call); when more than one call is configured, the diff is split into multiple review requests and findings are merged/deduped across all call results
  - *Note (added 2026-06-21, Phase 9 discussion):* single call is the baseline; multi-call addresses PRs too large for one context window or where parallel coverage improves quality. Default stays 1 (backward-compatible). Promoted from CUST-04 scope with broader framing — CUST-04 was budget-overflow only; this is a first-class configurable mode.
- [x] **ENGN-06**: When multi-call is active, the diff is split in a context-preserving way — files that share imports/references or belong to the same routed skill bundle must land in the same call to avoid losing cross-file context; exact splitting strategy is configurable (bundle-aligned is the default candidate)
  - *Note (added 2026-06-21, Phase 9 discussion):* bundle-aligned splitting (group files by their classified skill bundle) is the leading candidate because bundles already represent semantic cohesion; other strategies (call-graph, directory, size-balanced) are alternatives to consider during planning.
- [x] **ENGN-07**: When multi-call is active, calls can be executed in parallel (configurable concurrency, default 1 = sequential); parallel mode is opt-in because it multiplies token spend and adapter subprocess count
  - *Note (added 2026-06-21, Phase 9 discussion):* sequential default avoids surprise cost spikes; parallel is useful when latency matters more than cost. Concurrency cap prevents runaway subprocess count on large PRs.

### Output

- [x] **OUTP-01**: Review posts a sticky summary comment (updated in place on subsequent runs) with verdict, classification labels, and findings overview
- [x] **OUTP-02**: Review posts inline line-level comments via the Reviews API, with finding positions validated against diff hunks (invalid positions fall back to the summary)
- [x] **OUTP-03**: Review reports pass/fail/neutral status usable as a merge gate (blocking is opt-in via severity threshold)
- [x] **OUTP-04**: Summary comment includes token/cost transparency: tokens used, skills loaded vs skipped

### Noise Control

- [x] **NOIS-01**: Review skips draft PRs, bot authors (e.g. dependabot), and title/label-filtered PRs by default (configurable)
- [x] **NOIS-02**: Findings carry severity levels; consumer configures min-severity-to-comment and min-severity-to-fail thresholds
- [x] **NOIS-03**: Review enforces a hard per-review comment budget so the bot never floods a PR

### Security

- [x] **SECR-01**: Workflow uses the `pull_request` trigger only (no `pull_request_target`); fork PRs are documented as unsupported in v1
- [x] **SECR-02**: Untrusted PR text (titles, bodies, comments) is never interpolated into engine prompts as instructions; prompt-injection mitigations documented and tested

### Review Lifecycle

- [x] **LIFE-01**: Incremental review on new pushes (diff since last-reviewed SHA, stored in sticky-comment marker)
  - *Note (added 2026-06-14, Phase 7 discussion):* today a new push re-classifies AND re-reviews the entire PR even when the new commit doesn't touch earlier files — redundant token spend. Scope **both** classification and review to the incremental diff since the last-reviewed SHA. The "unless the new change addresses a prior finding" case is covered by LIFE-02 (dedupe) + LIFE-04 (resolve outdated threads). Cross-file call-graph impact ("a change here references a prior finding's function over there") stays out of scope — see "Full codebase graph/indexing" under Out of Scope.
  - *Promoted v2 → v1 on 2026-06-15: covered by Phase 8 (Incremental & Stateful Review Lifecycle).*
- [x] **LIFE-02**: Comment dedupe using existing PR comments as engine context plus deterministic fingerprint backstop
- [x] **LIFE-04**: Auto-resolve outdated inline threads when the underlying lines change
  - *Phase 8 shipped conservative resolve (region overlap + incremental scope only). v2 gaps below.*

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Review Lifecycle

- ~~**LIFE-03**: Manual `/review` comment trigger for re-runs~~ → **promoted to v1 (Phase 8)** 2026-06-16. Manual `/prevue review` / `/prevue dismiss` / `/prevue resolve` via `issue_comment`, write-assoc gated (CONTEXT D-16/D-17). Its base-context-execution + write-gating security review is now an in-phase requirement.
- ~~**LIFE-05**: Smarter inline thread lifecycle beyond conservative auto-resolve~~ → **promoted to v1 (Phase 8)** 2026-06-16. Full-review-authoritative auto-resolve + hybrid audited dismiss for persistent false positives (CONTEXT D-13/D-14/D-15).
  - *Dogfood on Phase 8 (PR #16) exposed gaps: fixing code does not dismiss stale inline threads; resolve/delete only runs when (a) file is in incremental `delta_paths`, (b) hunk region changed this push, and (c) engine did not re-report same fingerprint — carried open-set priors keep threads alive. Persistent false positives (engine re-emits same fingerprint each run) never auto-clear. Closed by D-13 (full-review engine-silence resolve) + D-14/D-15 (gated, auto-expiring, PR-scoped dismiss).*

### Customization & Scale

- **CUST-01**: Per-path severity/skill overrides for monorepos
- **CUST-02**: GitHub native `suggestion` blocks in findings for one-click apply
- ~~**CUST-03**: Second engine adapter (e.g. Claude Code, Gemini CLI) to validate the abstraction~~ → **promoted to ENGN-04 (v1, Phase 5)** 2026-06-13
- ~~**CUST-04**: Chunked map-reduce review for PRs exceeding the token budget~~ → **superseded by ENGN-05/06/07 (v1, Phase 9)** 2026-06-21. Broader framing: configurable multi-call mode (not only budget-overflow), context-preserving split strategy, and optional parallelism.
- **CUST-05**: Surface classification labels as native GitHub PR labels (opt-in) — cheap reuse of the existing zero-token classifier output
  - *Source (added 2026-06-15): Qodo PR-Agent `/generate_labels`.*
- **CUST-06**: Contributor-aware review profile — vary review stringency by `author_association` (e.g. a stricter, onboarding-oriented review for `FIRST_TIME_CONTRIBUTOR`/`NONE`) on PRs that already run under the `pull_request` trigger; no new permissions, no secret exposure.
  - *Scope note:* this covers only non-fork PRs that already execute. Giving **fork** PRs a restricted/no-secrets review path is the `pull_request_target` credential-theft class and stays **Out of Scope** — see that table below.
  - *Source (added 2026-06-25): anthropics/claude-code-action `if: author_association == 'FIRST_TIME_CONTRIBUTOR'` conditional review.*

### Review Quality

- **QUAL-01**: Per-finding confidence/impact scoring with intra-review dedup — score each finding, suppress low-confidence ones below a configurable threshold, and collapse overlapping findings on the same lines so a single review never emits near-duplicate comments (noise control; distinct from LIFE-02, which dedupes *across* pushes)
  - *Source (added 2026-06-15): Qodo PR-Agent `/improve` scores and self-filters suggestions.*
  - *Source (added 2026-06-25): anthropics/claude-code-action `classify_inline_comments` (buffer + filter low-value comments) + severity-gated posting — reinforces the threshold-before-post design.*
- **QUAL-02**: Ticket/issue compliance check — when a PR links an issue, verify the diff plausibly satisfies the issue's acceptance criteria and flag gaps (reads linked issue text only; no extra write scope)
  - *Source (added 2026-06-15): Qodo PR-Agent ticket-compliance tool.*

### Token Optimization

- **PERF-01**: Deterministic-tool-assisted prioritization — run cheap linters/SAST first and feed the engine only their hits plus surrounding context, shrinking review input and cutting false positives (extends the hybrid deterministic-first thesis from classification into the review step itself)
  - *Source (added 2026-06-15): CodeRabbit linter integration; GitHub "token efficiency in agentic workflows" — the cheapest LLM call is the one you don't make.*
- **PERF-02**: Diff packing/compression optimization — language-aware file prioritization, drop deleted-file bodies, and hunk-level compression before the engine call (complements CUST-04: compress first, split via map-reduce only if still over budget)
  - *Source (added 2026-06-15): Qodo PR-Agent PR-compression strategy.*
  - *Source (added 2026-06-25): candidate techniques — (a) **semantic chunking** via TreeSitter function/class units, feeding only relevant chunks (bobmatnyc/ai-code-review, claims 95%+ reduction on whole-codebase review); (b) **Headroom** local pre-LLM compression (AST CodeCompressor, JSON SmartCrusher, `CacheAligner` for KV-cache prefix hits, Python library mode). Caveat: both add heavy dependency surface against Prevue's lean thesis, and the headline reductions are measured on whole-file/codebase input, not diff-only review — **gate adoption behind a spike (see Backlog)** that measures real savings on Prevue's hunk-level input before phasing. Prefer library mode over Headroom's HTTP proxy (proxy doesn't fit the Copilot-CLI subprocess model).*
- **PERF-03**: Actual token accounting — replace the `bytes/4` estimate (`src/prevue/engines/tokens.py`, surfaced as "~est" in OUTP-04) with real token counts captured from each engine adapter's own usage reporting (input / output / cache tokens), falling back to estimation only when an engine does not report usage; optionally compute cost from a pricing database. Turns OUTP-04's "tokens used (~est)" into measured tokens + cost. The existing `token_meta.estimated` / `review_estimated` / `classify_estimated` flags already anticipate this swap.
  - *Source (added 2026-06-25): junhoyeo/tokscale — aggregates the usage AI CLIs already record (Claude Code JSONL `usage`, Codex `token_count`, etc.) and prices via the LiteLLM pricing DB; no tokenization, no estimation. Prevue's analog: have the adapter parse engine-reported usage from CLI output.*

### PR Authoring (opt-in)

- **DESC-01**: PR description assist — optionally generate a title/summary/walkthrough into the PR body, reusing the existing classification labels (opt-in; uses the `pull-requests: write` scope Prevue already holds, no new permissions)
  - *Source (added 2026-06-15): Qodo PR-Agent `/describe`; CodeRabbit walkthroughs.*

### Engine Adapter

- **ENGN-08**: Adapter raw-args passthrough — an explicit escape-hatch field on the adapter contract so engine-specific CLI flags can be passed through without changing Prevue's typed inputs; keeps the abstraction stable as new engines add flags.
  - *Source (added 2026-06-25): anthropics/claude-code-action `claude_args` passthrough; its multi-provider auth (Bedrock/Vertex/Foundry/direct) validates Prevue's pluggable-adapter bet.*
- **ENGN-09**: Per-role model tiering — let the adapter select different models per role (cheap classify → strong review → cheap consolidate/dedup) instead of one model for every call; pairs with ENGN-05 multi-call and PERF-01 to cut cost without losing review depth.
  - *Source (added 2026-06-25): bobmatnyc/ai-code-review separate "writer model" for cost-optimized consolidation.*

### Output

- **OUTP-05**: Structured machine-readable review output — emit the validated findings result (the existing pydantic `ReviewResult`) as a GitHub Actions job `output:` and/or JSON artifact, so consumers can chain automation (merge gates, dashboards) off the review. Cheap, and core to being a framework other repos build on.
  - *Source (added 2026-06-25): anthropics/claude-code-action structured JSON outputs become Action outputs for downstream automation.*
- **OUTP-06**: Live progress comment — post an in-progress sticky comment with checkboxes that update as the review proceeds and finalize on completion, improving perceived latency on large/slow reviews. Uses the `pull-requests: write` scope already held; keep edit cadence coarse (per-phase, not per-finding) to stay under secondary rate limits.
  - *Source (added 2026-06-25): anthropics/claude-code-action `track_progress`.*

### Skills

- **SKIL-05**: Additional built-in skill bundles beyond the core set (security/frontend/backend/data/infra) — candidates validated by ai-code-review's 16 review types: `extract-patterns` (surface reusable conventions), `evaluation` (rubric scoring), `unused-code` (dead-code/unreachable detection). Each is a SKILL.md bundle + routing rules; no framework change. Pick by consumer demand.
  - *Source (added 2026-06-25): bobmatnyc/ai-code-review review-type catalog.*

### Workflow Packaging

- **WKFL-05**: Declared config precedence for `prevue.yml` — define and test a single resolution order (workflow input > `.github/prevue.yml` > built-in defaults) before consumers depend on ambiguous behavior; precedence is hard to change once relied upon.
  - *Source (added 2026-06-25): bobmatnyc/ai-code-review config precedence hierarchy (CLI > project config > env > defaults).*

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Auto-fix / auto-commit of findings | Requires `contents: write`; destroys minimal-permissions trust model; write-capable agents on untrusted PR content is a documented attack surface |
| `pull_request_target` fork support | Base-repo secrets + untrusted PR content + LLM = documented credential-theft class (2026 CSA/MSRC research); two-workflow split deferred until real demand |
| Full codebase graph/indexing | Needs persistent state between runs; impossible in a stateless reusable workflow and opposed to the token-efficiency thesis |
| Learning from 👍/👎 reactions | Needs a backend to persist preference state; config-as-code (edit skill files) is the auditable alternative |
| Conversational `/ask` chat on PRs | Unbounded token spend; prompt-injection surface on attacker-writable comment text |
| LLM-only classification | Burns tokens on trivially classifiable PRs; non-deterministic routing is undebuggable — hybrid is non-negotiable |
| Non-GitHub platforms (GitLab, Bitbucket) | Contradicts "GitHub reusable workflow" identity; engine adapter is the portability layer that matters |
| Remote/central skill registry at runtime | Network/auth complexity; built-in + consumer-local skills cover v1 |
| IDE / local pre-push review mode | CI-first; may come later |
| Auto-approve / bot-submitted approving reviews | Escalates Prevue from an advisory pass/fail check (OUTP-03) to approving authority; a bot approval can satisfy branch protection and bypass human review intent — trust/safety regression (considered from PR-Agent self-review/auto-approve) |
| Suggestion-application analytics / acceptance tracking | Needs a persistent backend to store which suggestions were applied across runs — same stateless-workflow objection as 👍/👎 learning (considered from PR-Agent suggestion analytics) |
| Auto-commit of changelog/docstrings (`/update_changelog`, `/add_docs`) | Requires `contents: write`; same minimal-permissions objection as auto-fix (considered from PR-Agent authoring tools) |
| Conversational per-line `/ask_line` chat | Same unbounded-token + prompt-injection objection as `/ask` above (considered from PR-Agent) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DIFF-01 | Phase 1 | Complete |
| ENGN-01 | Phase 1 | Complete |
| ENGN-02 | Phase 1 | Complete |
| OUTP-01 | Phase 1 | Complete |
| SECR-01 | Phase 1 | Complete |
| DIFF-02 | Phase 2 | Complete |
| CLSF-01 | Phase 2 | Complete |
| CLSF-03 | Phase 2 | Complete |
| ROUT-01 | Phase 2 | Complete |
| SKIL-01 | Phase 3 | Complete |
| SKIL-02 | Phase 3 | Complete |
| SKIL-04 | Phase 3 | Complete |
| ENGN-03 | Phase 4 | Complete (04-02) |
| OUTP-02 | Phase 4 | Complete (04-04/04-05) |
| OUTP-03 | Phase 4 | Complete (04-05) |
| NOIS-02 | Phase 4 | Complete (04-03) |
| NOIS-03 | Phase 4 | Complete (04-03/04-05) |
| ENGN-04 | Phase 5 | Complete |
| WKFL-01 | Phase 6 | Complete |
| WKFL-02 | Phase 6 | Complete |
| WKFL-03 | Phase 6 | Complete |
| WKFL-04 | Phase 6 | Complete |
| CLSF-02 | Phase 6 | Complete |
| NOIS-01 | Phase 6 | Complete |
| SKIL-03 | Phase 7 | Complete |
| SECR-02 | Phase 7 | Complete |
| OUTP-04 | Phase 7 | Complete |
| DIFF-03 | Phase 7 | Complete |
| LIFE-01 | Phase 8 | Complete |
| LIFE-02 | Phase 8 | Complete |
| LIFE-04 | Phase 8 | Complete |
| LIFE-03 | Phase 8 | Complete (08-15) |
| LIFE-05 | Phase 8 | Complete (08-15) |
| SKIL-01 (gap) | Phase 9 | Complete |
| ENGN-05 | Phase 9 | Complete |
| ENGN-06 | Phase 9 | Complete |
| ENGN-07 | Phase 9 | Complete |

**Coverage:**

- v1 requirements: 33 total (added ENGN-05/06/07 2026-06-21)
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-12*
*Last updated: 2026-06-24 — Phase 9 complete; SKIL-01 gap + ENGN-05/06/07 traceability updated to Complete; UAT 14/14 pass*
*v2 expanded 2026-06-25 — research mining of ai-code-review, claude-code-action, headroom, tokscale: added CUST-06, ENGN-08/09, OUTP-05/06, SKIL-05, WKFL-05, PERF-03 (actual token tracking); folded compression/severity sources into PERF-02 + QUAL-01. Spike + consumer-doc tasks parked in ROADMAP Backlog.*
