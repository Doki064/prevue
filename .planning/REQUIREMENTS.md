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
- [ ] **DIFF-03**: Pipeline enforces a token budget with prioritized file packing and explicitly discloses "N files not reviewed" in the summary
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
- [ ] **SKIL-03**: Consumer repos can add custom skills and override built-in bundles via `.github/prevue/skills/`
- [x] **SKIL-04**: Skills are loaded from the trusted base ref only; PR-modified skill files are never executed in the same run

### Engine Adapter

- [x] **ENGN-01**: Engine adapters implement a pluggable interface: review context in → structured findings (file, line, severity, message, suggestion) out
- [x] **ENGN-02**: GitHub Copilot CLI adapter runs headless on Actions runners (`copilot -p ... -s --no-ask-user`, auth via `COPILOT_GITHUB_TOKEN`, minimal `--allow-tool` set)
- [x] **ENGN-03**: Engine output is schema-validated with retry-then-degrade handling; a parse failure produces a neutral check, never a crash or false block
- [ ] **ENGN-04**: Additional engine adapters (Claude Code CLI, Cursor CLI, Gemini CLI) implement the same pluggable interface and are selectable via config, validating the engine abstraction beyond Copilot (promoted from CUST-03, 2026-06-13)

### Output

- [x] **OUTP-01**: Review posts a sticky summary comment (updated in place on subsequent runs) with verdict, classification labels, and findings overview
- [x] **OUTP-02**: Review posts inline line-level comments via the Reviews API, with finding positions validated against diff hunks (invalid positions fall back to the summary)
- [x] **OUTP-03**: Review reports pass/fail/neutral status usable as a merge gate (blocking is opt-in via severity threshold)
- [ ] **OUTP-04**: Summary comment includes token/cost transparency: tokens used, skills loaded vs skipped

### Noise Control

- [x] **NOIS-01**: Review skips draft PRs, bot authors (e.g. dependabot), and title/label-filtered PRs by default (configurable)
- [x] **NOIS-02**: Findings carry severity levels; consumer configures min-severity-to-comment and min-severity-to-fail thresholds
- [x] **NOIS-03**: Review enforces a hard per-review comment budget so the bot never floods a PR

### Security

- [x] **SECR-01**: Workflow uses the `pull_request` trigger only (no `pull_request_target`); fork PRs are documented as unsupported in v1
- [ ] **SECR-02**: Untrusted PR text (titles, bodies, comments) is never interpolated into engine prompts as instructions; prompt-injection mitigations documented and tested

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Review Lifecycle

- **LIFE-01**: Incremental review on new pushes (diff since last-reviewed SHA, stored in sticky-comment marker)
- **LIFE-02**: Comment dedupe using existing PR comments as engine context plus deterministic fingerprint backstop
- **LIFE-03**: Manual `/review` comment trigger for re-runs
- **LIFE-04**: Auto-resolve outdated inline threads when the underlying lines change

### Customization & Scale

- **CUST-01**: Per-path severity/skill overrides for monorepos
- **CUST-02**: GitHub native `suggestion` blocks in findings for one-click apply
- ~~**CUST-03**: Second engine adapter (e.g. Claude Code, Gemini CLI) to validate the abstraction~~ → **promoted to ENGN-04 (v1, Phase 5)** 2026-06-13
- **CUST-04**: Chunked map-reduce review for PRs exceeding the token budget

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
| ENGN-04 | Phase 5 | Pending |
| WKFL-01 | Phase 6 | Complete |
| WKFL-02 | Phase 6 | Complete |
| WKFL-03 | Phase 6 | Complete |
| WKFL-04 | Phase 6 | Complete |
| CLSF-02 | Phase 6 | Complete |
| NOIS-01 | Phase 6 | Complete |
| SKIL-03 | Phase 7 | Pending |
| SECR-02 | Phase 7 | Pending |
| OUTP-04 | Phase 7 | Pending |
| DIFF-03 | Phase 7 | Pending |

**Coverage:**

- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-12*
*Last updated: 2026-06-12 after roadmap creation*
