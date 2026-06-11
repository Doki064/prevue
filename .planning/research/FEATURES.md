# Feature Research

**Domain:** AI PR review framework (delivered as a GitHub reusable workflow)
**Researched:** 2026-06-12
**Confidence:** HIGH (feature claims verified against official docs of CodeRabbit, Cursor Bugbot, GitHub Copilot code review, Claude Code Action, Greptile, Graphite Diamond, Qodo/pr-agent, Danger, reviewdog; security findings cross-checked across CSA, Microsoft Security Blog, and independent research)

## Competitor Landscape Summary

| Tool | Delivery | Defining trait |
|------|----------|----------------|
| CodeRabbit | GitHub App (SaaS) | Most complete comment-lifecycle UX: incremental reviews, `@coderabbitai` commands, `.coderabbit.yaml` |
| Cursor Bugbot | GitHub App (SaaS) | Reads existing PR comments to avoid duplicates; `.cursor/BUGBOT.md` rules; check states success/neutral/failure |
| GitHub Copilot code review | Native GitHub feature | Zero-install; `.github/copilot-instructions.md` + path-specific instructions (4,000-char limit per file, read from base branch) |
| Claude Code GitHub Action | GitHub Actions workflow | Closest architectural analog to Prevue: bring-your-own-workflow, inline comments via MCP tool, sticky comment option |
| Greptile | GitHub App (SaaS) | Codebase graph context; strictness 1–3 scale; cascading `.greptile/` config for monorepos; learns from 👍/👎 |
| Graphite Diamond | GitHub App (SaaS) | Custom rules + exclusions with per-rule acceptance-rate analytics |
| Qodo / pr-agent | Open source, runs in your CI | Single-LLM-call-per-tool design; best-documented large-PR compression/chunking strategy; `.pr_agent.toml` |
| Danger | CI script (non-AI) | Programmable PR-convention rules (Dangerfile); the deterministic baseline |
| reviewdog | CI tool (non-AI) | Pipes any linter output into PR comments/checks; diff-filtered to suppress noise |

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete. Every SaaS competitor has all of these.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Summary comment + inline line-level comments | Universal across all 7 AI tools; inline = actionability, summary = scanability | MEDIUM | Inline comments need correct diff-position mapping (file + line + side); GitHub Review API handles batching |
| Pass/fail GitHub Check | Merge-gating is the reason teams adopt CI review; Bugbot models it as success/neutral/failure | LOW | Neutral state matters: "found issues but not configured to block" avoids forcing teams into hard gates on day one |
| Triggered automatically on PR open + new pushes | CodeRabbit, Bugbot, Greptile, Diamond all auto-review on open and update | LOW | For Prevue this is the consumer's `workflow_call` trigger config — document recommended `pull_request: [opened, synchronize]` |
| Skip conditions: draft PRs, bot authors, title/label filters | CodeRabbit ships `drafts: false`, `ignore_usernames` (e.g. `dependabot[bot]`), title keywords (`WIP`), label excludes, base-branch filters; Bugbot skips drafts by default | LOW | Cheap to implement, severe annoyance if missing — bot-authored PRs (Dependabot, Renovate) waste tokens and trust |
| Path filters / ignore patterns | Every tool excludes lockfiles, vendored code, generated files, binaries by default; consumers extend with globs | LOW | Ship sensible defaults (lockfiles, `dist/`, `*.min.js`, images); allow override. Doubles as a token saver — Greptile reports 30–50% faster reviews from ignores alone |
| Repo-level config file in-repo | `.coderabbit.yaml`, `.cursor/BUGBOT.md`, `.github/copilot-instructions.md`, `greptile.json`, `.pr_agent.toml` — config-as-code is the norm | LOW | Single YAML file at a well-known path. Decide and document which branch config is read from (see Security) |
| Custom instructions / guidelines injection | All tools let teams add plain-language review guidance; Copilot caps at 4,000 chars, Bugbot supports hierarchical `BUGBOT.md` files | LOW | Prevue's skill-bundle model is a superset of this — consumer skills ARE the custom instructions |
| Severity levels on findings | Qodo exposes a severity-threshold rank for inline comments (critical → informational); Greptile strictness 1–3; users need to sort signal | MEDIUM | Require the engine to emit severity per finding; threshold filtering is then trivial |
| Noise threshold config (what severity blocks / comments) | "Untuned review bot is noise" is the #1 complaint pattern across all tools | LOW | Two knobs: min severity to post a comment, min severity to fail the check |
| Incremental review on new commits | CodeRabbit reviews only commits since last review (`auto_incremental_review`, default on); Copilot has "review new pushes"; re-reviewing everything per push is noise + token waste | HIGH | Requires state: last-reviewed SHA per PR (storable in a hidden HTML comment marker or check metadata). Compute diff between last-reviewed SHA and head |
| Don't duplicate existing comments | Bugbot explicitly reads top-level + inline PR comments as context to avoid duplicate suggestions | MEDIUM | Minimum viable: fetch existing bot comments, pass digests to engine with "do not repeat" instruction; exact-match dedupe by (file, line, fingerprint) as deterministic backstop |
| Manual trigger via PR comment (`/review` style) | `@coderabbitai review`, `cursor review`, `/review` (pr-agent) — every tool has an escape hatch when auto-review is off or stale | LOW | `issue_comment` trigger in consumer workflow; nice v1.x add, table stakes by v2 |

### Differentiators (Competitive Advantage)

Features that set Prevue apart. Aligned with the core value: token/context efficiency without losing review quality.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Hybrid classification → selective skill loading | THE differentiator. No competitor classifies the diff to load only relevant guidelines; they stuff everything into context (Copilot truncates at 4k chars; Bugbot users hit silent truncation on huge guideline files). Prevue bounds context per review by construction | HIGH | This is the product. Deterministic glob/path/lockfile pass first; cheap LLM only for ambiguous diffs. Token cost of classification must stay near-zero for clear-cut PRs |
| Pluggable engine adapter (Copilot CLI first) | Every SaaS competitor locks you to their model+billing. pr-agent supports multiple LLM APIs but not agentic CLI engines. "Bring the AI subscription you already pay for" is unique | MEDIUM | Adapter contract: prompt+skills in → structured findings (file, line, severity, message, suggestion) out. Copilot CLI headless (`copilot -p ... --no-ask-user`) verified workable |
| Runs in consumer's CI, no code leaves GitHub | SaaS tools ship your diff to their backend. Prevue runs on the consumer's runner with their token — a trust/compliance story SaaS can't match (only self-hosted Greptile Enterprise competes, at enterprise price) | LOW | Free consequence of the reusable-workflow architecture; market it deliberately |
| Token/cost transparency per review | No competitor reports what a review cost. Prevue's thesis is efficiency — prove it: report tokens used, skills loaded vs. skipped in the summary comment | LOW | Cheap to add, reinforces the core value every single review, builds trust in the classifier |
| Skill bundles as versioned, overridable directories | Bugbot's hierarchical BUGBOT.md and Greptile's cascading `.greptile/` config gesture at this, but neither has routable, self-contained skill packages. Consumer can add/override skills per repo without forking | MEDIUM | SKILL.md-style convention: directory of markdown + routing metadata. Depends on classifier labels being a stable public contract |
| Monorepo-aware routing | Greptile's cascading config is the only real monorepo story among competitors. Prevue's path-based classification gives per-package skill routing naturally (frontend PR in `packages/web` → frontend bundle only) | MEDIUM | Falls out of the classifier design if label rules support path scoping; make it explicit and documented |
| Deterministic-first design (auditable routing) | Competitors' "why did it comment on this?" is a black box. Prevue's glob/path classification is inspectable: the summary can state "classified as: backend, security — matched rules X, Y" | LOW | Free byproduct of hybrid classification; surfaces in the summary comment |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems. Documented to prevent scope creep.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Auto-fix / auto-commit of findings | Bugbot Autofix, Greptile "Fix All" are marketed heavily | Requires `contents: write` — destroys the minimal-permissions trust story; write-capable agents on untrusted PR content is the exact attack surface in the 2026 CSA/Microsoft CI-security findings | Review-only. Include suggested-fix code blocks in comments (GitHub native `suggestion` blocks let humans apply with one click) |
| Full codebase graph/index context | Greptile's headline feature; "more context = better review" intuition | Requires persistent indexing infrastructure + state between runs — impossible in a stateless reusable workflow, and directly opposed to the token-efficiency thesis | Targeted context expansion: let the engine adapter read surrounding files on demand (Copilot CLI can read the checked-out repo); skills tell it what to look for |
| Learning from 👍/👎 reactions | Greptile and Diamond both do feedback-driven suppression | Needs a backend storing per-team preference state; a GitHub-workflow-shaped product has nowhere to persist this | Config-as-code learning loop: false positive → consumer edits skill file or adds exclusion; auditable and versioned in git |
| `pull_request_target` for fork PR support | Fork PRs from `pull_request` trigger get no secrets, so reviews fail; `pull_request_target` "fixes" it | Categorically dangerous: base-repo secrets + untrusted PR content + an LLM interpreting that content = documented credential-theft attack class (CSA 2026, Microsoft MSRC 2026, "Comment and Control" research) | v1: document fork PRs as unsupported with `pull_request`. If demanded later: two-workflow split (unprivileged review job → artifact → privileged comment-poster job) |
| Reviewing every commit of every PR with full context | "Most thorough" default | Token waste compounds: 50 commits = 50 full reviews; this is the failure mode Prevue exists to fix | Incremental review (diff since last-reviewed SHA) + skip conditions + path filters as defaults |
| LLM-only classification | Simpler to build than the hybrid; "the model figures it out" | Burns tokens on every PR including trivially classifiable ones; non-deterministic routing makes skill loading unpredictable and undebuggable | The hybrid is non-negotiable: deterministic rules first, LLM fallback only for genuinely ambiguous diffs |
| Multi-platform support (GitLab, Bitbucket) | pr-agent supports 5 platforms; users will ask | Abstraction tax on every feature (comments, checks, diffs differ per platform); contradicts "GitHub reusable workflow" identity | Stay GitHub-native; the engine adapter is the portability layer that matters |
| Chat-with-the-bot on PRs (`/ask`, conversational replies) | pr-agent `/ask`, CodeRabbit conversations are popular | Each reply is a full engine invocation with context; open-ended chat is unbounded token spend and a prompt-injection surface on attacker-writable comment text | Defer entirely. A single manual `/review` re-trigger covers the real need |

## Cross-Cutting Topic Findings

### Comment behaviors (dedupe, incremental, outdated resolution)

- **Incremental review** (CodeRabbit's default): review only commits since the last reviewed SHA; offer full re-review as a manual command. Requires persisting last-reviewed SHA — feasible statelessly via a marker in the bot's own summary comment (query own comments, parse marker).
- **Dedupe**: Bugbot's approach — feed existing PR comments (top-level + inline) into review context with instructions not to repeat — is the practical pattern for an engine-adapter design. A deterministic fingerprint (file + line + normalized finding) catch is a cheap backstop.
- **Outdated-comment resolution**: CodeRabbit auto-considers prior comments in incremental runs and offers `@coderabbitai resolve`; Greptile resolves comments when a fix is pushed. Minimum bar for Prevue: update the sticky summary comment in place (Claude Code Action's `sticky_comment` pattern) instead of stacking a new summary per push; resolving inline threads whose lines changed is a v1.x enhancement via the GraphQL `resolveReviewThread` mutation.
- **Check conclusions**: Bugbot's three-state model (success / neutral-found-issues / failure-when-configured-to-block) is the right shape — blocking should be opt-in per severity threshold.

### Configuration UX

- Norm is a single config file in-repo: `.coderabbit.yaml` (YAML), `.pr_agent.toml` (TOML), `greptile.json` (JSON), `BUGBOT.md` / `copilot-instructions.md` (markdown prose). Prevue needs: one YAML config (thresholds, skip rules, path filters, classifier overrides) + skill directories (markdown).
- Org-level layering (Qodo's org repo `pr-agent-settings`, Greptile org defaults, Copilot org instructions) is a recurring enterprise ask — defer, but don't design the config loader in a way that precludes it.
- **Critical gotcha**: which ref config is read from. Copilot reads instructions from the *base* branch (security-correct: PR authors can't alter review rules); Greptile reads `greptile.json` from the *source* branch (convenient but attacker-influenceable). For Prevue, read config + skills from the base branch / trusted ref — this is both a security and correctness decision.

### Noise control / severity thresholds

- Greptile: strictness 1–3 + comment-type filters (logic/syntax/style/info). Qodo: numeric severity-threshold rank for inline comments. Graphite: exclusions with analytics on what each exclusion caught.
- Convergent pattern: (a) classify each finding by severity + category, (b) config sets minimum severity to comment and minimum to fail, (c) category filters (e.g., never comment on style). Prevue gets category control largely for free via skill selection — not loading the style skill means no style comments.

### Monorepo handling

- Greptile is the benchmark: cascading `.greptile/` config directories, per-package strictness overrides. CodeRabbit approximates with `path_instructions` (per-glob guidance).
- Prevue's classifier-as-router covers the core need (per-package skill bundles via path rules). Per-path severity overrides are a v1.x refinement.

### Large-PR handling

- pr-agent has the most mature published strategy: tiktoken-exact token budgeting; sort files by repo-language relevance then token count; pack until budget; overflow files become a names-only "other modified files" list; deletions added last; map-reduce chunking (`/improve --extended`) for oversized PRs; dynamic context expansion to the enclosing function/class rather than fixed line counts.
- For Prevue v1: a token budget per review, prioritized file packing, and an explicit "N files not reviewed (budget)" disclosure in the summary is enough. Chunked multi-call review is a v2 feature. Note the interaction: classification labels can prioritize which files matter most when the budget forces cuts.

### Security around untrusted PR code in CI

Highest-stakes area; 2026 incidents (Microsoft/MSRC on Claude Code Action, CSA research note, "Comment and Control" attack class) define the bar:

- **Never `pull_request_target` with checkout of fork code + AI processing.** The combination of base-repo secrets, untrusted content, and an LLM interpreting that content is the documented attack class.
- **Treat all PR-derived text as hostile data, not instructions**: PR title, body, comments, commit messages, file contents. Never interpolate `${{ github.event.* }}` into prompts; the system prompt must explicitly declare these surfaces untrusted.
- **Minimal token scopes**: `contents: read`, `pull-requests: write`, `checks: write`. No write access to code. This is already a Prevue constraint — keep it a hard invariant.
- **Strict engine tool allowlists**: Copilot CLI's `--allow-tool` must be a tight allowlist (no arbitrary shell); Claude Code Action's `--allowedTools` precedent confirms this is the expected control.
- **Validate engine output before acting on it**: parse findings against a strict schema before posting; never execute engine output as commands.
- **Config/skills from trusted ref only** (base branch), per the Copilot precedent above.
- Pin third-party actions to SHAs; document the trust model in README — security-conscious consumers will audit before adopting a reusable workflow that runs an AI agent.

## Feature Dependencies

```
Diff fetch (files + patches + metadata)
    └──required by──> Hybrid classifier (deterministic rules)
                          └──required by──> LLM classification fallback
                          └──required by──> Router (labels → bundles)
                                                └──required by──> Skill loader
                                                                      └──required by──> Engine adapter (Copilot CLI)
                                                                                            └──required by──> Output: summary + inline + check

Severity-per-finding (engine output schema) ──required by──> Noise thresholds (comment/fail gates)
Severity-per-finding ──required by──> Pass/fail check logic
Path filters / skip conditions ──gate──> entire pipeline (run before any token spend)
Sticky summary comment (marker) ──required by──> Incremental review (last-reviewed SHA storage)
Incremental review ──required by──> Outdated-comment resolution
Existing-comment fetch ──required by──> Dedupe
Classifier label contract (stable, documented) ──required by──> Consumer custom skills / overrides
Classifier path rules ──enables──> Monorepo routing
Token accounting in pipeline ──required by──> Token/cost transparency reporting
Engine adapter abstraction ──required by──> Any second engine (Claude Code, etc.)

pull_request_target ──conflicts──> minimal-permissions trust model (do not combine)
Full-codebase indexing ──conflicts──> stateless reusable workflow + token-efficiency thesis
```

### Dependency Notes

- **Severity schema must be in the engine adapter contract from day one**: noise thresholds, check pass/fail, and future analytics all consume it; retrofitting a structured findings schema after shipping a freeform first adapter is a rewrite.
- **Sticky summary comment before incremental review**: the summary comment is the natural stateless home for the last-reviewed-SHA marker; build the marker convention into the first version of the output stage even if incremental review ships later.
- **Stable label taxonomy before consumer skills**: once consumers write routing metadata against classification labels (security/frontend/backend/data/infra), renaming labels is a breaking change. Treat the label set as a versioned public API.
- **Skip conditions and path filters run first**: they are the cheapest token savings in the whole system — zero engine or classifier invocation for skipped PRs/files.

## MVP Definition

### Launch With (v1)

- [ ] Full pipeline: fetch diff → hybrid classify → route → load skills → Copilot CLI adapter → output — the product's reason to exist
- [ ] Summary comment + inline comments + pass/fail check with neutral state — universal output baseline
- [ ] Structured findings schema with severity (in adapter contract) — everything downstream depends on it
- [ ] Skip conditions (drafts, bot authors, title/label filters) + default path filters — cheap, expected, saves tokens
- [ ] Severity thresholds: min-to-comment, min-to-fail (blocking opt-in) — minimum viable noise control
- [ ] Single YAML config read from trusted ref — table-stakes config UX, security-correct
- [ ] Built-in skill bundles (security, frontend, backend, data, infra) + consumer override convention — the routing targets
- [ ] Security hardening: `pull_request` trigger only, minimal scopes, no event-text interpolation into prompts, engine tool allowlist, schema-validated output — non-negotiable for a workflow consumers must trust
- [ ] Sticky summary comment (update in place, embed review-state marker) — prevents summary spam; foundation for incremental review
- [ ] Token budget with prioritized file packing + "not reviewed" disclosure — minimum large-PR honesty
- [ ] Token/skills-loaded transparency line in summary — trivial cost, proves the core value every review

### Add After Validation (v1.x)

- [ ] Incremental review on new pushes — trigger: users complain about repeat reviews / token spend on multi-commit PRs (highest-value fast-follow; CodeRabbit treats it as default-on)
- [ ] Comment dedupe via existing-comment context — trigger: duplicate findings reported after incremental lands
- [ ] Manual `/review` comment trigger — trigger: users want re-runs without pushing
- [ ] Resolve outdated inline threads when lines change — trigger: stale-comment complaints
- [ ] Per-path severity/skill overrides (monorepo refinement) — trigger: monorepo adopters
- [ ] GitHub native `suggestion` blocks in findings — trigger: "one-click apply" requests

### Future Consideration (v2+)

- [ ] Chunked map-reduce review for PRs exceeding budget — defer: complexity high, prioritized packing covers most cases
- [ ] Second engine adapter (Claude Code, Gemini CLI, ...) — defer: validates adapter abstraction, but one solid adapter proves the product
- [ ] Org-level shared config/skill repo — defer: enterprise ask, needs adoption first
- [ ] Two-workflow privileged-split for fork PR support — defer: real demand unproven; high security design cost
- [ ] Review analytics (acceptance rates per skill/rule, Graphite-style) — defer: needs volume of usage data to be meaningful

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Pipeline (classify→route→load→review) | HIGH | HIGH | P1 |
| Summary + inline + check output | HIGH | MEDIUM | P1 |
| Severity schema + noise thresholds | HIGH | MEDIUM | P1 |
| Skip conditions + path filters | HIGH | LOW | P1 |
| Security hardening (trigger, scopes, injection) | HIGH | MEDIUM | P1 |
| YAML config from trusted ref | HIGH | LOW | P1 |
| Built-in skill bundles + overrides | HIGH | MEDIUM | P1 |
| Sticky summary comment | MEDIUM | LOW | P1 |
| Token transparency reporting | MEDIUM | LOW | P1 |
| Token budget / file packing | MEDIUM | MEDIUM | P1 |
| Incremental review | HIGH | HIGH | P2 |
| Comment dedupe | MEDIUM | MEDIUM | P2 |
| Manual `/review` trigger | MEDIUM | LOW | P2 |
| Outdated-thread resolution | MEDIUM | MEDIUM | P2 |
| Monorepo per-path overrides | MEDIUM | MEDIUM | P2 |
| Suggestion blocks | MEDIUM | LOW | P2 |
| Chunked large-PR review | MEDIUM | HIGH | P3 |
| Second engine adapter | MEDIUM | MEDIUM | P3 |
| Fork PR support (privileged split) | LOW | HIGH | P3 |
| Org-level config | LOW | MEDIUM | P3 |

**Priority key:** P1 = must have for launch · P2 = should have, add when possible · P3 = nice to have, future

## Competitor Feature Analysis

| Feature | CodeRabbit | Bugbot | Copilot CR | Greptile | pr-agent | Our Approach |
|---------|------------|--------|------------|----------|----------|--------------|
| Incremental review | Default on, since-last-SHA | Re-runs per push, reads prior comments | Opt-in "review new pushes" | `triggerOnUpdates` flag | `push_commands` | v1.x: SHA marker in sticky comment, diff since last review |
| Dedupe | Incremental considers prior comments | Reads all PR comments as context | — | Learning suppresses repeats | — | Existing-comment context + fingerprint backstop (v1.x) |
| Noise control | Path filters + instructions | BUGBOT.md "what to leave alone" | Custom instructions only | Strictness 1–3 + comment types | Severity threshold rank | Severity thresholds + skill selection as category filter |
| Config | `.coderabbit.yaml` | `.cursor/BUGBOT.md` + dashboard | `.github/*.md` (4k char cap, base branch) | `greptile.json` / cascading `.greptile/` | `.pr_agent.toml` (3-level) | One YAML + skill dirs, read from trusted ref |
| Monorepo | `path_instructions` globs | Hierarchical BUGBOT.md | Path-specific instruction files | Cascading per-dir config | — | Path-scoped classifier rules → per-package bundles |
| Large PRs | — (SaaS-managed) | — (SaaS-managed) | — (SaaS-managed) | Graph narrows scope | Token-aware packing + chunking | Budgeted packing + disclosure; chunking v2 |
| Skip conditions | Drafts, authors, titles, labels, branches | Drafts off by default, once-per-PR option | Draft opt-in | `skipReview` | Per-command auto config | Full CodeRabbit-style matrix in YAML |
| Untrusted-code security | SaaS boundary | SaaS boundary | GitHub-native boundary | SaaS boundary | Runs in your CI (user's risk) | `pull_request` only, minimal scopes, no event-text in prompts, tool allowlist |
| Engine choice | Their models | Their models | Copilot only | Their models | Any LLM API | Pluggable agentic-CLI adapters (unique) |
| Selective context loading | — | — | — (truncates at 4k) | Graph retrieval | Diff compression | Classify → load only matched skills (unique) |

## Sources

- CodeRabbit docs — auto-review config, review commands, path filters/instructions (docs.coderabbit.ai) — HIGH confidence
- Cursor Bugbot docs (cursor.com/docs/bugbot) + practitioner write-ups (WorkOS, Steve Kinney) — HIGH/MEDIUM
- GitHub Copilot code review docs — concepts, custom instructions, 4k limit, base-branch behavior (docs.github.com) — HIGH
- Claude Code GitHub Action — repo docs, solutions.md, sticky_comment PR #211, issue #1108 (github.com/anthropics/claude-code-action) — HIGH
- Greptile docs — key features, controlling nitpickiness, greptile.json reference, graph context, llms.txt (greptile.com) — HIGH
- Graphite Diamond docs — customization, rules & exclusions analytics (graphite.com/docs); Braintrust case study — HIGH/MEDIUM
- Qodo/pr-agent docs — compression strategy, dynamic context, automations, .pr_agent.toml hierarchy (docs.pr-agent.ai, docs.qodo.ai) — HIGH
- Danger JS (danger.systems / github.com/danger/danger-js); reviewdog (github.com/reviewdog) — HIGH
- CI security: CSA research note on AI GitHub Actions prompt injection (2026-05); Microsoft Security Blog on Claude Code Action secret exposure (2026-06); "Comment and Control" research (Lyrie, 2026-05); Aikido PromptPwnd; HackTricks pull_request_target — HIGH (cross-verified across independent sources)

---
*Feature research for: AI PR review framework (GitHub reusable workflow)*
*Researched: 2026-06-12*
