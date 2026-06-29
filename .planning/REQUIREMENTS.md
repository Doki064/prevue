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
- [x] **WKFL-05** *(Phase 10)*: Declared config precedence for `prevue.yml` — define and test a single resolution order (workflow input > `.github/prevue.yml` > built-in defaults) before consumers depend on ambiguous behavior; precedence is hard to change once relied upon.
  - *Promoted v2 → v1 on 2026-06-25 (Phase 10 — Boundary Contracts). Source: bobmatnyc/ai-code-review config precedence hierarchy.*

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
- [ ] **SKIL-06** *(Phase 11)*: Extract the built-in skill bundles into a **dedicated skills repo**, consumed by Prevue as a **git submodule pinned to a SHA** — which doubles as the **default built-in skill source** (Prevue ships pointing at the pinned submodule; zero-config consumers get the defaults). Decouples skill-content authoring/versioning/contribution from framework code and makes the bundles portable, while preserving the SKIL-04 trust model: a pinned ref is trusted exactly like the framework checkout — **pin-at-checkout, NOT a runtime registry**. The label taxonomy (security/frontend/backend/data/infra) becomes a **versioned contract** between the two repos. Skill source is a config value defaulting to the bundled submodule pin (shared mechanism with SKIL-07).
  - *Promoted v2 → v1 on 2026-06-25 (Phase 11 — Skills as Pinned External Repo). Reopens OOS "Remote/central skill registry at runtime" — resolved by pinned submodule, not dynamic lookup.*
- [ ] **SKIL-07** *(Phase 11)*: Consumer can point Prevue at an **external skills repo** via config/input — the same config knob as SKIL-06's default, overridden — alongside consumer-local custom skills (SKIL-03, unchanged). **Security-gated, non-negotiable:** skills are instructions injected into a privileged LLM holding secrets, so an external source MUST be pinned by SHA and trusted to the same bar as framework code; floating tags / `main` / runtime mutable fetch are forbidden (prompt-injection / instruction-hijack surface). Likely an allowlist + mandatory pin + documented trust model; the arbitrary-repo full form may land behind a gate.
  - *Promoted v2 → v1 on 2026-06-25 (Phase 11). Admissible only under mandatory pin + trust gating.*

### Engine Adapter

- [x] **ENGN-01**: Engine adapters implement a pluggable interface: review context in → structured findings (file, line, severity, message, suggestion) out
- [x] **ENGN-02**: GitHub Copilot CLI adapter runs headless on Actions runners (`copilot -p ... -s --no-ask-user`, auth via `COPILOT_GITHUB_TOKEN`, minimal `--allow-tool` set)
- [x] **ENGN-03**: Engine output is schema-validated with retry-then-degrade handling; a parse failure produces a neutral check, never a crash or false block
- [x] **ENGN-04**: Additional engine adapters (Claude Code CLI, Cursor CLI, Gemini CLI) implement the same pluggable interface and are selectable via config, validating the engine abstraction beyond Copilot (promoted from CUST-03, 2026-06-13)
- [x] **ENGN-08** *(Phase 10)*: Adapter raw-args passthrough — an explicit escape-hatch field on the adapter contract so engine-specific CLI flags can be passed through without changing Prevue's typed inputs; keeps the abstraction stable as new engines add flags.
  - *Promoted v2 → v1 on 2026-06-25 (Phase 10). Source: anthropics/claude-code-action `claude_args` passthrough.*
- [x] **ENGN-09** *(Phase 10)*: Per-role model tiering — let the adapter select different models per role (cheap classify → strong review → cheap consolidate/dedup) instead of one model for every call; pairs with ENGN-05 multi-call and PERF-01 to cut cost without losing review depth. Enables the cheap dedup/scoring pass QUAL-01 (Phase 13) relies on.
  - *Promoted v2 → v1 on 2026-06-25 (Phase 10). Source: bobmatnyc/ai-code-review separate "writer model" for consolidation.*
- [x] **ENGN-10** *(Phase 10 — FIRST task)*: Consolidate the CLI engine adapters into a **spec-driven generic adapter** (declarative `CliEngineSpec`: secret env + validator, argv, prompt-delivery {stdin|tempfile-arg}, model-flag {env|argv}, cli_label, cwd, functional flag), or a template-method base at minimum. Today `copilot_cli.py` / `cursor_cli.py` / `claude_code_cli.py` repeat identical `review`/`classify`/`classify_skills` wiring — only ~4 axes vary — and `registry.py` requires a manual import + dict entry per engine. The generic adapter implements those methods once; the registry auto-populates from the spec list; `gemini` skeleton becomes `functional=False` (drops the `SKELETON_ENGINES` special-case). **Must land before PERF-03 / ENGN-08 / ENGN-09**, which are all adapter-contract changes that otherwise cost 4× (one edit per existing adapter) instead of 1×.
  - *Migration caveats: preserve per-engine `AuthError` subclasses (tests assert on type); repoint `copilot_cli.__all__` internal re-exports relied on by tests; `classify_skills` becomes available to every engine for free. Recommend spec-driven; template-method base is the low-risk fallback.*
  - *Source (added 2026-06-25): adapter-layer review — shared flow/prompt/subprocess already factored; remaining per-adapter file is boilerplate shell.*
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
- [x] **OUTP-05** *(Phase 10)*: Structured machine-readable review output — emit the validated findings result (the existing pydantic `ReviewResult`) as a GitHub Actions job `output:` and/or JSON artifact, so consumers can chain automation (merge gates, dashboards) off the review. Cheap, and core to being a framework other repos build on.
  - *Promoted v2 → v1 on 2026-06-25 (Phase 10). Source: anthropics/claude-code-action structured JSON outputs.*

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
  - *Phase 8 shipped conservative resolve (region overlap + incremental scope only).*
- [x] **LIFE-03**: Manual `/prevue review` / `/prevue dismiss` / `/prevue resolve` comment triggers via `issue_comment`, write-association gated (CONTEXT D-16/D-17); base-context execution + write-gating security review handled in-phase.
  - *Promoted v2 → v1 2026-06-16 (Phase 8 — 08-15); relocated from v2 into v1 on 2026-06-25.*
- [x] **LIFE-05**: Smarter inline thread lifecycle beyond conservative auto-resolve — full-review-authoritative auto-resolve + hybrid audited dismiss for persistent false positives (CONTEXT D-13/D-14/D-15).
  - *Promoted v2 → v1 2026-06-16 (Phase 8 — 08-15); relocated from v2 into v1 on 2026-06-25.*

### Token Optimization

- [x] **PERF-03** *(Phase 10)*: Actual token accounting — replace the `bytes/4` estimate (`src/prevue/engines/tokens.py`, surfaced as "~est" in OUTP-04) with real token counts captured from each engine adapter's own usage reporting (input / output / cache tokens), falling back to estimation only when an engine does not report usage; optionally compute cost from a pricing database. Turns OUTP-04's "tokens used (~est)" into measured tokens + cost. The existing `token_meta.estimated` / `review_estimated` / `classify_estimated` flags already anticipate this swap.
  - *Promoted v2 → v1 on 2026-06-25 (Phase 10). Source: junhoyeo/tokscale — aggregates usage AI CLIs already record (Claude Code JSONL `usage`, Codex `token_count`), prices via LiteLLM; no tokenization, no estimation.*
- [ ] **PERF-04** *(Phase 12)*: Selective cross-file dependency context — when a changed file references a first-party symbol whose definition lives in an **unchanged** file (not in the diff), pull that definition into review context so the engine can catch contract violations it otherwise cannot see. A **whole-framework** gap, not just incremental: Prevue reviews the diff, which never contains unchanged dependencies regardless of incremental mode (demonstrated 2026-06-25 — a PR touching only `checkout.py` could not see `MAX_CHARGE_AMOUNT = 9999.99` in unchanged `processor.py`; review missed the missing-cap bug). Resolution stays **selective** — same discipline as skill-loading: **depth-1, first-party imports of changed files only**, capped (per-file byte budget, max-N files); never transitive/full-graph (Out-of-Scope "full codebase graph/indexing"). Infra already exists: the workflow checks out the consumer base ref to disk (`PREVUE_CONSUMER_ROOT`, trusted), and `src/prevue/importscan.py` already resolves first-party paths — the missing link is `multicall.py` discarding a resolved path not in the changed set (`if target_path in known_paths`) instead of reading it as reference context. Third-party imports stay excluded (importscan returns `[]` for them).
  - *Implementation ladder (earn each step with measured token data): (a) **Capped-A** — inject the whole resolved dependency file as labeled read-only context; dumb-simple, lossless per file, language-agnostic; bound by depth-1 + byte/file caps; ship first and measure. (b) **Symbol-slice (option D)** — only if capped-A's bill is too high: ast-parse, slice the referenced symbol's full body + one-hop module-level name closure + class state + decorator/comment lines; Python-first (stdlib `ast`), JS/TS need tree-sitter (heavy dep → later). Silent-miss boundary for (b): constraint behind a deeper helper call, inherited base method, or dynamic dispatch — out of depth-1 scope by design.*
  - *Promoted v2 → v1 on 2026-06-25 (Phase 12). Source: live tier-2 gap demo (test-sandbox-repo PR #11); builds on Phase 9 importscan (ENGN-06). Distinct from PERF-01/02 (those shrink the reviewed diff; PERF-04 adds adjacent unchanged context).*

### Review Quality

- [ ] **QUAL-01** *(Phase 13)*: Per-finding confidence/impact scoring with intra-review dedup — score each finding, suppress low-confidence ones below a configurable threshold, and collapse overlapping findings on the same lines so a single review never emits near-duplicate comments (noise control; distinct from LIFE-02, which dedupes *across* pushes). Uses the cheap scoring/dedup model role from ENGN-09.
  - *Promoted v2 → v1 on 2026-06-25 (Phase 13). Source: Qodo PR-Agent `/improve` self-filtering; anthropics/claude-code-action `classify_inline_comments` + severity-gated posting.*

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Review Lifecycle

- ~~**LIFE-03**~~ → **relocated to v1 → Review Lifecycle (Phase 8, complete)** 2026-06-25.
- ~~**LIFE-05**~~ → **relocated to v1 → Review Lifecycle (Phase 8, complete)** 2026-06-25.

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

- ~~**QUAL-01**: Per-finding confidence/impact scoring with intra-review dedup~~ → **promoted to v1 (Phase 13 — Finding Signal Quality)** 2026-06-25.
- **QUAL-02**: Ticket/issue compliance check — when a PR links an issue, verify the diff plausibly satisfies the issue's acceptance criteria and flag gaps (reads linked issue text only; no extra write scope)
  - *Source (added 2026-06-15): Qodo PR-Agent ticket-compliance tool.*

### Token Optimization

- **PERF-01**: Deterministic-tool-assisted prioritization — run cheap linters/SAST first and feed the engine only their hits plus surrounding context, shrinking review input and cutting false positives (extends the hybrid deterministic-first thesis from classification into the review step itself)
  - *Source (added 2026-06-15): CodeRabbit linter integration; GitHub "token efficiency in agentic workflows" — the cheapest LLM call is the one you don't make.*
- **PERF-02**: Diff packing/compression optimization — language-aware file prioritization, drop deleted-file bodies, and hunk-level compression before the engine call (complements CUST-04: compress first, split via map-reduce only if still over budget)
  - *Source (added 2026-06-15): Qodo PR-Agent PR-compression strategy.*
  - *Source (added 2026-06-25): candidate techniques — (a) **semantic chunking** via TreeSitter function/class units, feeding only relevant chunks (bobmatnyc/ai-code-review, claims 95%+ reduction on whole-codebase review); (b) **Headroom** local pre-LLM compression — installable Apache-2.0 Python library (`pip install headroom-ai`, `from headroom import compress`), runs fully on-device, no cloud account/API key; offers AST `CodeCompressor`, JSON `SmartCrusher`, and `CacheAligner` for KV-cache prefix hits. Dependency caveat is in the **optional extras**: `[all]`/`[ml]` pull ONNX Runtime + a HuggingFace `kompress-base` model download, but that model serves *prose* — code compression is AST-based and a slim/code-only install may skip it. Both techniques' headline reductions (95%+) are measured on whole-file/codebase input, not diff-only review. **Gate adoption behind a spike (see Backlog)** that measures real savings on Prevue's hunk-level input AND the minimal install footprint before phasing. Prefer library mode over Headroom's HTTP proxy (proxy doesn't fit the Copilot-CLI subprocess model).*
- ~~**PERF-03**: Actual token accounting (engine-reported usage replaces bytes/4)~~ → **promoted to v1 (Phase 10 — Boundary Contracts)** 2026-06-25.
- ~~**PERF-04**: Selective cross-file dependency context (depth-1 first-party, capped-A → symbol-slice)~~ → **promoted to v1 (Phase 12 — Cross-File Dependency Context)** 2026-06-25.

### PR Authoring (opt-in)

- **DESC-01**: PR description assist — optionally generate a title/summary/walkthrough into the PR body, reusing the existing classification labels (opt-in; uses the `pull-requests: write` scope Prevue already holds, no new permissions)
  - *Source (added 2026-06-15): Qodo PR-Agent `/describe`; CodeRabbit walkthroughs.*

### Engine Adapter

- ~~**ENGN-08**: Adapter raw-args passthrough~~ → **promoted to v1 (Phase 10 — Boundary Contracts)** 2026-06-25.
- ~~**ENGN-09**: Per-role model tiering (cheap classify / strong review / cheap consolidate)~~ → **promoted to v1 (Phase 10 — Boundary Contracts)** 2026-06-25.

### Output

- ~~**OUTP-05**: Structured machine-readable review output (`ReviewResult` as Actions output/JSON)~~ → **promoted to v1 (Phase 10 — Boundary Contracts)** 2026-06-25.
- **OUTP-06**: Live progress comment — post an in-progress sticky comment with checkboxes that update as the review proceeds and finalize on completion, improving perceived latency on large/slow reviews. Uses the `pull-requests: write` scope already held; keep edit cadence coarse (per-phase, not per-finding) to stay under secondary rate limits.
  - *Source (added 2026-06-25): anthropics/claude-code-action `track_progress`.*

### Skills

- **SKIL-05**: Additional built-in skill bundles beyond the core set (security/frontend/backend/data/infra) — candidates validated by ai-code-review's 16 review types: `extract-patterns` (surface reusable conventions), `evaluation` (rubric scoring), `unused-code` (dead-code/unreachable detection). Each is a SKILL.md bundle + routing rules; no framework change. Pick by consumer demand.
  - *Source (added 2026-06-25): bobmatnyc/ai-code-review review-type catalog.*
- ~~**SKIL-06**: Skills → dedicated repo as SHA-pinned git submodule = default source~~ → **promoted to v1 (Phase 11 — Skills as Pinned External Repo)** 2026-06-25.
- ~~**SKIL-07**: Consumer-specified external skills repo (pin + trust gated)~~ → **promoted to v1 (Phase 11 — Skills as Pinned External Repo)** 2026-06-25.

### Distribution & Local Surface

- **LOCL-01**: Skills (portable agentskills.io bundles once SKIL-06 lands) are invocable as **interactive agent-skill slash commands** (e.g. `/prevue review frontend`) outside the CI workflow, for local / pre-push review — a **second delivery surface** alongside the reusable workflow. Note this **bypasses auto-classification** (manual skill selection), so it is a thinner, manual variant of the core classify→route→load pipeline, not a replacement. Enabled by SKIL-06's portable bundles.
  - *Source (added 2026-06-25): skills-rework discussion. Reopens OOS "IDE / local pre-push review mode."*

### Workflow Packaging

- ~~**WKFL-05**: Declared config precedence for `prevue.yml`~~ → **promoted to v1 (Phase 10 — Boundary Contracts)** 2026-06-25.

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
| Remote/central skill registry at runtime | Network/auth complexity; built-in + consumer-local skills cover v1. **Reopened 2026-06-25 → SKIL-06/07 (v2):** admissible as a **pinned-SHA git submodule / pinned external repo**, never a dynamic runtime registry. The "runtime registry" exclusion still stands; pin-at-checkout does not. |
| IDE / local pre-push review mode | CI-first; may come later. **Reopened 2026-06-25 → LOCL-01 (v2):** interactive agent-skill slash commands as a second surface, enabled by SKIL-06 portable bundles. |
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
| ENGN-10 | Phase 10 | Complete |
| WKFL-05 | Phase 10 | Complete |
| PERF-03 | Phase 10 | Complete |
| ENGN-08 | Phase 10 | Complete |
| ENGN-09 | Phase 10 | Complete |
| OUTP-05 | Phase 10 | Complete |
| SKIL-06 | Phase 11 | Planned |
| SKIL-07 | Phase 11 | Planned |
| PERF-04 | Phase 12 | Planned |
| QUAL-01 | Phase 13 | Planned |
| CUST-01 | v2 | Deferred |
| CUST-02 | v2 | Deferred |
| CUST-03 | v2 | Superseded → ENGN-04 (Phase 5, Complete) |
| CUST-04 | v2 | Superseded → ENGN-05/06/07 (Phase 9, Complete) |
| CUST-05 | v2 | Deferred |
| CUST-06 | v2 | Deferred |
| QUAL-02 | v2 | Deferred |
| PERF-01 | v2 | Deferred |
| PERF-02 | v2 | Deferred |
| DESC-01 | v2 | Deferred |
| OUTP-06 | v2 | Deferred |
| SKIL-05 | v2 | Deferred |
| LOCL-01 | v2 | Deferred |

**Coverage:**

- v1 requirements: 43 (33 prior + 9 promoted 2026-06-25 + ENGN-10 adapter consolidation)
- Mapped to phases: 43 (Phases 1–9 Complete; Phase 10 Complete; Phases 11–13 Planned)
- v2 deferred: 11 (CUST-01/02/05/06, QUAL-02, PERF-01/02, DESC-01, OUTP-06, SKIL-05, LOCL-01) + 2 superseded (CUST-03/04)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-12*
*Last updated: 2026-06-29 — Phase 10 complete (ENGN-10/WKFL-05/PERF-03/ENGN-08/ENGN-09/OUTP-05 → Complete); added 13 missing v2 rows to Traceability table (CUST-01/02/03/04/05/06, QUAL-02, PERF-01/02, DESC-01, OUTP-06, SKIL-05, LOCL-01). Phase 9 complete: SKIL-01 gap + ENGN-05/06/07 → Complete; UAT 14/14 pass.*
*v2 expanded 2026-06-25 — research mining of ai-code-review, claude-code-action, headroom, tokscale: added CUST-06, ENGN-08/09, OUTP-05/06, SKIL-05, WKFL-05, PERF-03 (actual token tracking); folded compression/severity sources into PERF-02 + QUAL-01. Spike + consumer-doc tasks parked in ROADMAP Backlog.*
*PERF-04 added 2026-06-25 — selective cross-file dependency context (capped-A → symbol-slice ladder, depth-1 first-party); proven a whole-framework (not just incremental) gap via live tier-2 demo on test-sandbox-repo PR #11.*
*Skills rework 2026-06-25 — added SKIL-06 (skills → dedicated repo as pinned git submodule = default built-in source), SKIL-07 (consumer external skills repo, pin+trust gated), LOCL-01 (interactive slash-command surface); reopened two OOS rows as pinned-not-registry / local-surface. Considered and DROPPED: domain-composite skills + language-axis routing (`/review-web-app`, `--python`) — composites are sugar over existing multi-label routing; not pursued.*
*Roadmap + promotion 2026-06-25 — added Phases 10–13 to ROADMAP. Promoted 9 reqs v2 → v1 (prioritized by cost-of-delay — adapter/config contracts first): Phase 10 Boundary Contracts (WKFL-05, PERF-03, ENGN-08/09, OUTP-05), Phase 11 Skills as Pinned Repo (SKIL-06/07), Phase 12 Cross-File Dependency Context (PERF-04), Phase 13 Finding Signal Quality (QUAL-01). Relocated LIFE-03/05 from v2 into v1 (Phase 8, complete). Remaining v2 (CUST-01/02/05/06, QUAL-02, PERF-01/02, DESC-01, OUTP-06, SKIL-05, LOCL-01) stay deferred.*
*ENGN-10 added 2026-06-25 (v1, Phase 10 first task) — consolidate CLI adapters into a spec-driven generic before PERF-03/ENGN-08/ENGN-09, so those adapter-contract changes cost 1× not 4×.*
