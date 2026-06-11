# Project Research Summary

**Project:** Prevue
**Domain:** Token-efficient AI PR review framework delivered as a GitHub reusable workflow
**Researched:** 2026-06-12
**Confidence:** HIGH

## Executive Summary

Prevue is an AI PR review framework in a market dominated by SaaS GitHub Apps (CodeRabbit, Cursor Bugbot, Greptile, Graphite Diamond) and one open-source CI-native reference (Qodo pr-agent). Experts build these systems as a layered pipeline with two abstraction seams — a git-provider seam (fetch diff, post results) and an AI-engine seam (run the review) — and pr-agent's architecture confirms this shape works in production. Prevue follows the same shape but replaces the universal "compress everything to fit" context strategy with hybrid classify→route→load selective skill loading. That selective loading is the genuine differentiator: no competitor classifies the diff to load only relevant guidelines, and the two SaaS leaders either truncate (Copilot caps instructions at 4k chars) or silently choke on large guideline files.

The recommended approach is a thin reusable workflow (~50 lines of YAML, zero logic) over a fat Python CLI: PyGithub for the API, pydantic models as stage contracts, pathspec for gitignore-exact glob classification, python-frontmatter for Agent Skills-spec SKILL.md bundles, and a `subprocess`-based Copilot CLI adapter behind an `EngineAdapter` ABC. Stages communicate through typed JSON artifacts (DiffBundle → Classification → RoutingPlan → ReviewContext → ReviewResult), which makes every stage independently testable and replayable — critical because GitHub Actions iteration loops are slow and `workflow_call` cannot be meaningfully tested locally (act support is broken).

The key risks are security and trust, in that order. This product is exactly the shape of the 2026 CI attack class: secrets + untrusted PR content + an LLM interpreting that content. The non-negotiables are `pull_request` trigger only (fork PRs unsupported in v1), skills/config loaded from the trusted base ref only, a strict engine tool allowlist, and schema-validated engine output with the model having zero GitHub write capability. The second product-killing risk is review noise: untuned AI reviewers see 70–90% of comments ignored and get abandoned. Mitigation must be in code, not just prompts: hard comment budgets, severity thresholds, non-blocking checks by default, and infra failures surfacing as neutral — never as a red X.

## Key Findings

### Recommended Stack

Python 3.12+ with uv-managed dependencies, delivered as a `workflow_call` reusable workflow (correct vs composite action because the unit of reuse is a whole job with its own auditable `permissions:` block and explicit named secrets). All versions verified against PyPI/npm/official docs on the research date.

**Core technologies:**
- **PyGithub 2.9.1**: GitHub REST API — battle-tested standard; covers `get_files()`, batched `create_review(comments=[...])`, stable API for a framework other repos depend on
- **GitHub Copilot CLI 1.0.x (`@github/copilot`, npm)**: first engine adapter — verified headless mode (`copilot -p ... -s --no-ask-user --allow-tool=...`), auth via `COPILOT_GITHUB_TOKEN`; invoked via stdlib `subprocess`, no wrapper library needed
- **pydantic 2.13.x**: typed stage contracts and adapter I/O — validation at exactly the boundaries that matter (engine output, consumer config)
- **pathspec 1.1.x**: gitignore-exact `**` glob semantics for the deterministic classifier — stdlib `fnmatch` silently misclassifies; note 1.x renamed the pattern factory ("gitwildmatch" → "gitignore")
- **unidiff 0.7.5 + python-frontmatter 1.3.0**: diff-hunk parsing for inline-comment position validation; SKILL.md frontmatter parsing per the Agent Skills open spec (agentskills.io)
- **uv + ruff + pytest + responses**: dev toolchain; `responses` mocks PyGithub's `requests` layer cleanly

Critical packaging fact: a reusable workflow ships **only its YAML** — the workflow must self-checkout the prevue repo via `job.workflow_repository`/`job.workflow_sha` to get its Python code and skills. Avoid: ghapi/github3.py (unmaintained), LangChain (massive surface for a subprocess call), custom skill formats (Agent Skills is the open standard), act as primary test strategy (`workflow_call` support broken).

### Expected Features

Every SaaS competitor ships the same table-stakes set; missing them makes the product feel incomplete. Prevue's differentiators all flow from the classify→route→load thesis.

**Must have (table stakes):**
- Summary comment + inline line-level comments + pass/fail check (with neutral state) — universal output baseline
- Skip conditions (drafts, bot authors like Dependabot, title/label filters) + default path filters (lockfiles, generated, vendored) — cheap, expected, and the cheapest token savings in the system
- Single YAML config in-repo, read from the **base branch** (security-correct; Copilot's precedent) — config-as-code is the norm
- Severity per finding in the adapter contract + noise thresholds (min-to-comment, min-to-fail) — retrofitting a structured schema later is a rewrite
- Sticky summary comment updated in place (embeds review-state marker) — prevents summary spam; foundation for incremental review
- Token budget with prioritized file packing + explicit "N files not reviewed" disclosure

**Should have (competitive differentiators):**
- Hybrid classification → selective skill loading — THE product; no competitor does it
- Pluggable engine adapter ("bring the AI subscription you already pay for") — unique vs model-locked SaaS
- Runs in consumer's CI, no code leaves GitHub — trust/compliance story SaaS can't match
- Token/cost transparency line per review (skills loaded vs skipped) — proves the core value every review
- Deterministic, auditable routing ("classified as: backend, security — matched rules X, Y")
- Monorepo-aware routing via path-scoped classifier rules

**Defer (v1.x / v2+):**
- Incremental review since last-reviewed SHA (highest-value fast-follow), comment dedupe, manual `/review` trigger, suggestion blocks — v1.x
- Chunked map-reduce review, second engine adapter, org-level config, fork-PR privileged split — v2+
- Anti-features to refuse: auto-fix/auto-commit (destroys minimal-permissions trust), full codebase indexing (impossible stateless + contradicts thesis), `pull_request_target` (documented attack class), LLM-only classification, multi-platform, chat-with-bot

### Architecture Approach

A staged pipeline in one Python process, orchestrated by a thin reusable workflow. Each stage is a pure-ish function over pydantic models, writing JSON artifacts (`diff.json`, `classification.json`, `routing.json`, `review.json`) to `$RUNNER_TEMP` for replay and debugging (`prevue review --from-stage route`). The engine adapter is the only component that knows AI vendors exist; it returns a structured `ReviewResult` and **never** posts to GitHub — the deterministic, tested output writer owns every GitHub write. Skill injection is pipeline-owned prompt assembly, not engine-native discovery (native discovery re-delegates the selection decision the classifier already made, killing both determinism and pluggability). Pass/fail = process exit code → job status (Checks API rich features are GitHub-App-only).

**Major components:**
1. **Reusable workflow** (`review.yml`) — `workflow_call` interface, self-checkout of prevue + consumer repo, zero logic
2. **Diff fetcher** — paginated `GET /pulls/{n}/files` → `DiffBundle`; owns truncation policy as first-class metadata
3. **Hybrid classifier** — chain-of-responsibility: exact-path → glob/extension → content-pattern rules (data-driven `default_rules.yml`); LLM fallback only for unmatched files, via the adapter's `classify()` hook with minimal payload
4. **Router + skill loader** — labels → bundles with precedence (consumer override > consumer custom > built-in); reads SKILL.md bundles for routed labels only
5. **Engine adapter (ABC) + CopilotCliAdapter** — `review(ReviewContext) -> ReviewResult` via subprocess; prompt assembly adapter-owned
6. **Output validator + writer** — validates every finding against parsed diff hunks (degrade out-of-hunk findings to summary), posts one batched review via `POST /pulls/{n}/reviews`, sets exit code

### Critical Pitfalls

1. **`pull_request_target` + untrusted code = secret exfiltration** — the most exploited Actions misconfiguration, and Prevue is exactly its shape (needs secrets + untrusted diff + write perms). Decide trust architecture in phase 1: same-repo-only v1, diff fetched via API (never a checked-out executable tree in a privileged job).
2. **Prompt injection incl. via the skills system itself** — "Comment and Control" (2026) hijacked Claude/Gemini/Copilot review agents via PR titles and hidden HTML comments; GitInject showed config/skill files load as operator-level instructions. Load skills from trusted ref only, skip skills the PR modifies, minimal `--allow-tool`, fence untrusted text, strip HTML comments, schema-validate output.
3. **Review noise destroys trust** — the most common way AI review tools die (<30–40% comment-action-rate → abandonment). Hard comment budget (≤5–10 inline), severity floors, negative constraints in every skill, non-blocking check by default; enforce in code.
4. **Inline comment position mapping** — LLMs reason in file lines, the Reviews API accepts only diff-visible `line`/`side` tuples; unvalidated findings mean 422s and lost reviews. Build the diff-position validator as a first-class component; budget multiple days.
5. **Copilot CLI auth in Actions** — requires a fine-grained **user-owned** PAT with Copilot Requests permission (classic PATs unsupported; `GITHUB_TOKEN` shadows via lookup order and fails confusingly). Validate token presence/prefix before review; map failures to actionable setup errors; spike on a real runner early — highest-unknown integration in the project.
6. **Flaky LLM structured output** — never parse stdout; have the engine write findings to a file, validate with pydantic, retry once, degrade to summary-only. Parse failure = neutral check, never a red X.

## Implications for Roadmap

Research converges on a build order that follows the pipeline forward, with the engine adapter spiked early because it is the riskiest external integration.

### Phase 1: Foundation — models, config, GitHub client, diff fetcher
**Rationale:** `models.py` is the contract every other stage codes against; the diff fetcher makes the system observable end-to-end (`prevue fetch --pr N`). The workflow security model (trigger matrix, permissions block, same-repo-only posture) must be decided here — it is brutally expensive to retrofit.
**Delivers:** Typed stage contracts (DiffBundle etc.), `PrevueConfig` fan-in, paginated diff fetching with truncation metadata, trust-architecture decision documented.
**Addresses:** Diff fetch requirement; config-from-trusted-ref groundwork.
**Avoids:** Pitfall 1 (`pull_request_target`), Pitfall 2 (fork-PR posture), Pitfall 8 (pagination/missing-patch handling from day one).

### Phase 2: Deterministic classifier + router
**Rationale:** Pure functions over DiffBundle, fully unit-testable with fixture diffs, zero external risk. Proves the zero-token path — the core thesis — before any AI is involved.
**Delivers:** Chain-of-responsibility rules engine, data-driven `default_rules.yml`, label→bundle router with precedence, `llm_calls_made` metric.
**Uses:** pathspec (gitignore semantics), pydantic models from Phase 1.
**Avoids:** Pitfall 8 (pre-filtering lockfiles/generated/vendored is a classifier concern); LLM-only classification anti-feature.

### Phase 3: Skill loader + built-in bundles (machinery first, content thin)
**Rationale:** Establishes the SKILL.md convention and ReviewContext assembly that the adapter consumes. Bundle content can start thin (security/backend); the loading/resolution machinery is what matters.
**Delivers:** Agent Skills-spec bundle loading, built-in vs consumer merge/override resolution, ReviewContext assembly with token budget.
**Implements:** Skill loader/resolver component; trusted-ref loading invariant.
**Avoids:** Pitfall 3 (skill-file injection — trusted-ref loading designed in, not patched on).

### Phase 4: Engine adapter interface + Copilot CLI adapter
**Rationale:** Highest integration risk in the project (auth on runners, structured output reliability, timeouts). **Spike `copilot -p` on a real Actions runner during Phases 1–2** even though the full adapter lands here; the ReviewResult shape blocks Phases 5–6.
**Delivers:** `EngineAdapter` ABC + registry, CopilotCliAdapter with file-based output contract, schema validation, retry + summary-only degradation, auth pre-validation with actionable errors.
**Uses:** subprocess + pydantic; `--allow-tool` minimal allowlist.
**Avoids:** Pitfalls 7 (auth), 9 (flaky output), 3 (tool lockdown, fenced untrusted content).

### Phase 5: Output validator + writer
**Rationale:** Depends on Phase 4's ReviewResult shape. The diff-position validator is core correctness, not polish — budget real time for hunk parsing.
**Delivers:** Finding↔diff validation with summary fallback for out-of-hunk findings, single batched create-review call, sticky-comment idempotency marker, exit-code gate with neutral-on-infra-error semantics, comment budget + severity threshold enforcement.
**Avoids:** Pitfalls 4 (422s/wrong lines), 5 (noise — enforced in code), 6 (non-blocking default, neutral for pipeline errors), 11 (batched posting beats secondary rate limits).

### Phase 6: Reusable workflow + consumer config surface + LLM fallback classifier
**Rationale:** Wires the thin YAML (self-checkout via `job.workflow_sha`, dual checkout, install, invoke) and `prevue.yml` parsing. The LLM fallback slots in here because it reuses the Phase 4 adapter. **First shippable milestone** — a zero-config consumer can adopt.
**Delivers:** `workflow_call` interface with explicit named secrets and declared permissions, consumer YAML config, hybrid classification complete, end-to-end review of a real PR from a consumer repo.
**Avoids:** Pitfall 10 (test from a separate consumer repo; tag releases immediately; never document `@main` or `secrets: inherit`).

### Phase 7: Customization surface + remaining bundles + hardening
**Rationale:** The "framework, not tool" milestone — depends on the consumer checkout path being live.
**Delivers:** Consumer custom skills + override precedence in production, remaining built-in bundles (frontend/data/infra) with negative constraints baked in, prompt-injection red-team verification, large-PR truncation tuning, token-transparency summary line, skip conditions matrix.
**Avoids:** Pitfalls 3 (red-team verification), 5 (skill negative constraints), 8 (budget tuning).

### Phase Ordering Rationale

- **Phases 1–3 are pure-Python with no external risk** — they build the artifact spine fast and prove the zero-token classification path before any AI integration.
- **The engine adapter (Phase 4) is deliberately spiked early but landed mid-roadmap**: its ReviewResult contract blocks output work, and Copilot auth on runners is the project's highest unknown.
- **Security decisions front-load into Phases 1, 3, and 4** (trigger model, trusted-ref skill loading, tool allowlist) because all three are architectural and unretrofittable.
- **Output discipline (Phase 5) lands before the public interface (Phase 6)** so the first external consumer never experiences the noise/422/red-X failure modes that destroy trust.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (engine adapter):** Copilot CLI behavior on clean Actions runners — auth flow, `GITHUB_TOKEN` shadowing, output reliability, timeout behavior. Run a walking-skeleton spike during Phases 1–2.
- **Phase 5 (output):** diff-hunk → commentable `(path, line, side)` mapping edge cases (renames, multi-hunk files, large-file missing patches). Known multi-day rabbit hole; pr-agent's production issues are the reference.

Phases with standard patterns (skip research-phase):
- **Phases 1–3:** pure Python over well-documented GitHub REST endpoints, pathspec, and the published Agent Skills spec — patterns fully documented in STACK.md/ARCHITECTURE.md.
- **Phase 6:** `workflow_call` mechanics are exhaustively documented (official docs + PITFALLS.md gotcha list); execution care, not research, is what's needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified live against PyPI/npm/official GitHub docs on research date |
| Features | HIGH | Verified against official docs of 9 competitors; security findings cross-checked across 3+ independent sources |
| Architecture | HIGH/MEDIUM | GitHub mechanics HIGH (official docs); overall composition MEDIUM — synthesized from pr-agent's proven shape plus first-principles design for the skill-routing layer, which no existing tool implements |
| Pitfalls | HIGH | GitHub-documented behaviors verified officially; community failure modes cross-checked across multiple independent sources |

**Overall confidence:** HIGH

### Gaps to Address

- **Copilot CLI on clean runners (the one genuinely unverified integration):** docs verified, but real-runner behavior (auth edge cases, output stability under `-s`, timeout handling) needs the Phase 1–2 spike. Handle: walking-skeleton spike before Phase 4 planning.
- **Skill-routing layer has no production precedent:** the classify→route→load composition is first-principles design (MEDIUM confidence). Handle: keep the label taxonomy small and versioned as a public API; validate routing quality during dogfooding before encouraging consumer custom skills.
- **LLM-fallback classification quality/cost:** the threshold for "ambiguous" and the minimal-payload prompt are undesigned. Handle: design during Phase 6 planning; `llm_calls_made` metric from Phase 2 provides the measurement hook.
- **Noise calibration numbers:** budget defaults (≤5–10 comments, severity floors) come from community reports, not Prevue data. Handle: dogfood and measure comment-action-rate before v1 announce; make budgets config from day one.
- **act cannot test `workflow_call`:** local workflow testing is limited to a push-trigger wrapper + static checkers (actionlint, zizmor). Handle: stand up a consumer test repo as part of Phase 6.

## Sources

### Primary (HIGH confidence)
- GitHub official docs — Copilot CLI programmatic mode/auth/Actions automation; reusable workflows (`workflow_call` secrets/permissions/contexts); Pull request Reviews REST API (`line`/`side`, batched comments); Checks API (App-only)
- PyPI/npm registries — live version verification for all chosen packages (2026-06-12)
- agentskills.io specification — SKILL.md frontmatter schema
- Competitor official docs — CodeRabbit, Cursor Bugbot, GitHub Copilot code review, Claude Code Action, Greptile, Graphite Diamond, Qodo/pr-agent, Danger, reviewdog
- Security research (cross-verified) — "Comment and Control" (2026), CSA research note (2026-05), Microsoft Security Blog (2026-06), Orca "Pull Request Nightmare", CodeQL/OpenSSF untrusted-checkout guidance

### Secondary (MEDIUM confidence)
- PR-Agent architecture deep-dives (DeepWiki) — layered pipeline + compression strategy reference
- GitInject (arXiv 2026) — config/skill-file injection class, directly applicable to skill loading
- nektos/act maintainer statements — `workflow_call` limitations
- Community AI-review noise analyses (≥5 independent sources) — false-positive rates, comment-action-rate thresholds

### Tertiary (LOW confidence)
- Practitioner blog posts on reusable-workflow patterns — consistent with official docs but individually anecdotal

---
*Research completed: 2026-06-12*
*Ready for roadmap: yes*
