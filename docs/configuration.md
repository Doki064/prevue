<!-- generated-by: gsd-doc-writer -->
# Configuration

Consumer settings live in `.github/prevue.yml` on the **trusted base ref** (default branch at review time — not the PR head). Prevue reads the file once per run via `load_config()` and validates every section with Pydantic (`extra: forbid` — unknown keys fail at load).

If the file is missing, framework defaults apply (including `classification.fallback.enabled: true`). A stderr notice is emitted so silent LLM classify calls are not a surprise.

**Custom workflow integrators:** set `PREVUE_CONSUMER_ROOT` to a checkout of the base ref. Without it in GitHub Actions, consumer config is ignored (SKIL-04 fail-closed). See [consumer-setup.md](./consumer-setup.md).

## Quick reference

| Section | Purpose |
|---------|---------|
| `ignore` | Drop paths from the diff before classification |
| `labels` | Map file globs → classification labels (pack priority input) |
| `routing` | Map labels → bundle ids; drives hybrid skill selection for routed bundles |
| `review` | Token budget, severity thresholds, inline cap, incremental lifecycle, multi-call caps |
| `skip` | Skip review for bots, labels, or title regexes |
| `skills` | Consumer skill caps and exclusions |
| `classification.fallback` | LLM classify for unmatched paths |
| `engine` | Review engine adapter name |

Override config path with `PREVUE_CONFIG_PATH` (default `.github/prevue.yml`), resolved under `PREVUE_CONSUMER_ROOT` with traversal rejected.

## `ignore`

Additive gitignore-style globs merged **on top of** built-in noise filters. Built-in filters (from `src/prevue/classify/default_rules.yml`) exclude lockfiles (`**/*.lock`, `**/uv.lock`, `**/Cargo.lock`, etc.), minified assets (`**/*.min.js`, `**/*.min.css`), generated directories (`**/dist/**`, `**/build/**`, `**/vendor/**`, `**/node_modules/**`), and binary formats (`**/*.png`, `**/*.jpg`, `**/*.gif`, `**/*.pdf`, `**/*.woff2`).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `ignore` | list of globs | built-ins only | Paths matching any glob are removed from the diff before classification and review |

```yaml
ignore:
  - ".planning/**"
  - "docs/generated/**"
```

Matched files are dropped entirely — they are not classified, packed, or sent to the engine.

## `labels`

Per-label glob lists used for deterministic classification and pack priority. Consumer entries **replace** that label's built-in globs (not merged). Multiple labels can match a single file; canonical priority order applies when a file needs to be dropped under budget.

**Built-in labels** (from `src/prevue/classify/default_rules.yml`):

| Label | Default globs |
|-------|--------------|
| `security` | `**/auth/**`, `**/*.pem`, `**/.env*`, `**/secrets/**` |
| `frontend` | `**/*.tsx`, `**/*.jsx`, `**/*.vue`, `**/*.css`, `**/*.scss` |
| `backend` | `**/*.py`, `**/*.go`, `**/*.rb`, `**/*.java` |
| `data` | `**/migrations/**`, `**/*.sql`, `**/schema.prisma` |
| `infra` | `**/*.tf`, `terraform/**`, `**/Dockerfile`, `.github/workflows/**`, `**/k8s/**` |

Unmatched paths become `general` (lowest pack priority).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `labels.<name>` | list of globs | see `default_rules.yml` | Files matching any glob under `<name>` receive that label |

```yaml
labels:
  security:
    - "**/auth/**"
    - "**/*secret*"
    - "**/.env*"
  frontend:
    - "apps/web/**"
    - "**/*.tsx"
```

**Pack priority:** canonical rank determines drop order when the diff exceeds `review.max_input_tokens`. Priority: `security` → `frontend` → `backend` → `data` → `infra` → `general`.

**Limitation — whole-run budget cap:** classify and LLM-classify both run on the full filtered file set before packing, so pack priority uses the merged labels. Remaining risk: whole-run `max_total_run_tokens` (D-10) can still drop the lowest-priority files after skill selection. Mitigation: add explicit `labels` globs for high-risk path patterns (e.g. `**/auth/**`, `**/*secret*`), or raise `review.max_input_tokens`.

## `routing`

Maps classification labels to skill **bundle** directory names. Default: each label maps to a bundle of the same name (empty `routing` map).

**Why routing matters:** classification runs on the full changed file set (pre-pack). `route()` maps labels to bundle ids, and skills inside a routed bundle are evaluated for relevance via hybrid selection (`select_skills_hybrid`). Routed bundles close the SKIL-01 gap: a security-bundle skill loads even when no changed path matches its `applies-to` glob, as long as the PR is classified to the security bundle.

- **Routed bundles** → skills selected via keyword floor + LLM escalation (bundle-scoped).
- **Non-routed bundles** → skills selected by `applies-to` path globs only.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `routing.<label>` | string (bundle id) | `<label>` | Bundle id for skill selection + sticky `Bundles:` line when label is present |

```yaml
routing:
  frontend: react-app
  backend: python-api
```

Multiple labels can map to one bundle; duplicates are deduplicated in canonical label order.

## `review`

Gate thresholds, token budget, and incremental review lifecycle (`ReviewConfig` in `src/prevue/gate.py`).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_input_tokens` | int (1–250000) | `120000` | Per-call prompt token budget (~bytes/4 heuristic). Diff packing target before engine invoke |
| `output_reserve_tokens` | int (≥0) | `12000` | Tokens reserved for engine output per call; must be ≤ `max_input_tokens` and ≤ `max_tokens_per_call` |
| `min_severity_to_comment` | `error` \| `warning` \| `info` | `warning` | Minimum severity posted as inline or summary comment |
| `min_severity_to_fail` | `error` \| `warning` \| `info` \| null | `null` | Check conclusion `failure` when any finding meets this severity; `null` = never fail (neutral only) |
| `max_inline_comments` | int (≥0) | `10` | Cap on inline review comments across all calls; overflow goes to summary |
| `incremental` | bool | `true` | After first review, subsequent pushes review only the delta since the last sticky marker SHA |
| `resolve_outdated` | bool | `true` | Auto-resolve prior inline threads whose line regions no longer overlap the incremental diff |
| `max_known_issues` | int (≥0) | `20` | Prior open findings injected into the prompt as known issues (dedupe guidance) |
| `max_dismissals` | int (≥0) | `50` | Cap on persisted `/prevue dismiss` entries in the sticky comment |
| `max_review_calls` | int (≥1) | `1` | Maximum engine calls per PR review run. Default `1` = single-call (pre-multi-call behavior unchanged) |
| `max_tokens_per_call` | int (1–250000) | `120000` | Per-call input token ceiling when `max_review_calls > 1`; must be ≤ `max_total_run_tokens` |
| `max_total_run_tokens` | int (≥1) | `500000` | Whole-run token ceiling: classify + Σ review call tokens ≤ cap. Overflow drops lowest-priority files |
| `review_concurrency` | int (≥1) | `1` | Parallel engine call cap. Default `1` = sequential. Set to `max_review_calls` for full parallelism |
| `guardrail_skills` | list of `bundle/filename.md` | `[]` | Skill keys always included in every call regardless of per-group selection (security backstop) |

```yaml
review:
  max_input_tokens: 120000
  output_reserve_tokens: 12000
  min_severity_to_comment: warning
  min_severity_to_fail: null
  max_inline_comments: 10
  incremental: true
  resolve_outdated: true
  max_known_issues: 20
  max_dismissals: 50
  # Multi-call caps (all optional; defaults preserve single-call behavior)
  max_review_calls: 1
  max_tokens_per_call: 120000
  max_total_run_tokens: 500000
  review_concurrency: 1
  guardrail_skills: []
```

### Budget behavior

Effective diff budget = `max_input_tokens` minus prompt overhead (skills, instructions, known-issues block). `max_input_tokens` default stays under the ~250k-token stdin guard (`MAX_PROMPT_BYTES` = 1,000,000 bytes in `src/prevue/engines/prompt.py`). Oversized PRs pack whole files by risk weight; skipped files are disclosed in the sticky comment summary.

**`min_severity_to_fail` is independent of `min_severity_to_comment`** — fail conclusion evaluates all findings regardless of comment threshold.

**Incremental behavior:** `/prevue review` forces a full re-review regardless of `incremental`. Same-SHA re-runs are no-ops even when `incremental: false`.

**`resolve_outdated` requires `contents: write`** on the workflow token (verified live, 2026-06). If you cannot grant write scope, set `resolve_outdated: false`; incremental scoping and carry-forward still work.

### Token budget validation

Pydantic enforces three constraints at load time:

- `output_reserve_tokens` ≤ `max_input_tokens`
- `max_tokens_per_call` ≤ `max_total_run_tokens`
- `output_reserve_tokens` ≤ `max_tokens_per_call`

Violations raise a load error before any engine call runs.

## `skip`

Skip policy evaluated before engine spend (`SkipConfig` in `src/prevue/config.py`).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `review_bots` | list of logins | `[]` | **Allowlist** of bot logins to review; any other bot-authored PR is skipped. Empty = all bots skipped |
| `skip_labels` | list of strings | `["skip-review"]` | PR labels that skip review |
| `skip_title_patterns` | list of regex strings | `[]` | PR title patterns that skip review (Python `re` syntax, validated at config load) |

```yaml
skip:
  review_bots:
    - release-please[bot]   # only listed bots are reviewed; all other bots skipped
  skip_labels:
    - skip-review
    - wip
  skip_title_patterns:
    - "^\\[skip prevue\\]"
    - "^WIP:"
```

Invalid regex in `skip_title_patterns` raises a load error. Skipped PRs still get a neutral `prevue/review` check with the skip reason in the sticky comment — review is never silently absent.

## `skills`

Consumer skill configuration (`SkillsConfig` in `src/prevue/config.py`). Consumer skills live in `.github/prevue/skills/<bundle>/<filename>.md` on the base ref. See [skills.md](./skills.md) for the full SKILL.md frontmatter format.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `exclude` | list of `bundle/filename.md` | `[]` | Exact skill keys to disable (not globs). Applies to both built-in and consumer skills |
| `max_skill_bytes` | int (≥1) | `65536` | Per-skill body cap (64 KiB). Skills whose file size exceeds this are skipped before reading |
| `max_total_consumer_bytes` | int (≥1) | `262144` | Aggregate consumer skill body cap (256 KiB). Skills loaded after this threshold is hit are skipped |
| `max_consumer_skills` | int (≥1) | `50` | Max consumer skill files loaded per PR. Skills beyond this count are skipped |

```yaml
skills:
  exclude:
    - security/committed-secrets.md
  max_skill_bytes: 65536
  max_total_consumer_bytes: 262144
  max_consumer_skills: 50
```

Caps apply to **consumer skills only** — built-in skills (bundled in the framework package) are always loaded without caps. Skipped and excluded skills are disclosed in the sticky comment. A typo in an `exclude` key matches nothing and is logged to stderr; it does not fail the run.

## `classification.fallback`

Hybrid LLM classify for paths with no deterministic label match (`FallbackConfig` in `src/prevue/config.py`).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `classification.fallback.enabled` | bool | `true` | Run LLM classify on unmatched paths in the full filtered file set (pre-pack budget) |
| `classification.fallback.model` | string \| null | `null` | Model passed to the engine adapter for classify; `null` uses `PREVUE_MODEL` or `COPILOT_MODEL` from the workflow environment |

```yaml
classification:
  fallback:
    enabled: true
    model: null
```

When disabled or unavailable, unmatched paths fall back to the `general` label. LLM classify runs on the **full filtered set before the pack budget is applied** (D-01) — paths later dropped by the pack budget may still incur classify tokens. LLM classify never runs on files dropped by `ignore`.

Batching: classify calls are chunked at 100 paths per call (`CLASSIFY_BATCH_SIZE` in `src/prevue/classify/llm_fallback.py`). A partial classify failure (some paths unresolved) is disclosed in the sticky comment.

## `engine`

Selects the AI review adapter.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `engine.name` | string | `copilot-cli` | Registered adapter name |

```yaml
engine:
  name: copilot-cli
```

**Precedence:** `PREVUE_ENGINE` environment variable overrides `engine.name`; both override the framework default (`copilot-cli`). Source: `_resolve_engine()` in `src/prevue/config.py`.

### `engine.models` — per-role model overrides

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `engine.models.classify` | string \| null | `null` | Model used for the classify call; falls back to `engine.model` when unset |
| `engine.models.review` | string \| null | `null` | Model used for the review call; falls back to `engine.model` when unset |
| `engine.models.consolidate` | string \| null | `null` | Reserved for Phase 13 (QUAL-01); not consumed by the review pipeline today |

```yaml
engine:
  name: copilot-cli
  models:
    classify: gpt-4o-mini
    review: gpt-4o
```

Each role resolves as: `engine.models.<role>` else `engine.model` else the framework/engine default. `EngineModels` uses `extra="forbid"` — unknown keys under `models:` are rejected at config-load time.

### `engine.raw_args` — extra CLI flags

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `engine.raw_args` | list of strings | `[]` | Extra CLI flags appended after the framework's own argv when invoking the engine adapter |

```yaml
engine:
  raw_args:
    - "--some-flag"
    - "value"
```

List form only — a shell string (e.g. `raw_args: "--foo bar"`) is rejected with a `ValidationError` (D-10: command-injection guard; no shell parsing, no `shell=True`). Every element must be a string; non-string elements (`None`, numbers, booleans) are also rejected rather than silently coerced.

### `engine.pricing` — cost-table override

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `engine.pricing.<model>` | mapping \| null | `null` | Per-model pricing row that shadows the vendored pricing table when computing review cost |

```yaml
engine:
  pricing:
    gpt-4o:
      input_cost_per_token: 0.0000025
      output_cost_per_token: 0.00001
```

Each row must be a mapping (or `null`) of LiteLLM-style field names (`input_cost_per_token`, `output_cost_per_token`, `cache_read_input_token_cost`, `cache_creation_input_token_cost`); a malformed row (e.g. a scalar instead of a mapping) is rejected with a `ValidationError` at config-load time rather than crashing the review run.

`engine.raw_args` and `engine.pricing` are read from the same base-ref-only gated `load_config()` path as the rest of `prevue.yml` (SKIL-04): a PR-head `prevue.yml` cannot supply raw CLI flags or fake pricing data — only the base-ref (trusted) config is honored.

### Available engines

| Engine name | Status | Required secret | Auth env var |
|-------------|--------|-----------------|-------------|
| `copilot-cli` | Functional (default) | `copilot-github-token` | `COPILOT_GITHUB_TOKEN` — must be a fine-grained user-owned PAT (`github_pat_…`) with Copilot Requests permission |
| `claude-code-cli` | Functional | `claude-code-oauth-token` | `CLAUDE_CODE_OAUTH_TOKEN` — long-lived token from `claude setup-token` |
| `cursor-cli` | Functional | `cursor-api-key` | `CURSOR_API_KEY` |
| `antigravity-cli` | Registered, not functional — no headless/non-interactive auth exists for the `agy` CLI per official docs; review attempts fail closed with a clear error | — | `ANTIGRAVITY_API_KEY` |

**Review model:** the recommended override is the reusable workflow's `model` input (`with: model: ...`), which threads into `PREVUE_MODEL` for you. Alternatively, set `PREVUE_MODEL` or `COPILOT_MODEL` directly in the workflow environment (e.g. via a repository variable, for consumers who prefer not to edit their caller `with:` block per-call) — `PREVUE_MODEL` takes precedence; `COPILOT_MODEL` is the fallback (Copilot adapter). This is separate from `classification.fallback.model`.

**Engine install versions** (from `.github/scripts/install-engine-cli.sh`):

| Engine | Installed package | Version |
|--------|-------------------|---------|
| `copilot-cli` | `@github/copilot` (npm) | `1.0.61` |
| `claude-code-cli` | `@anthropic-ai/claude-code` (npm) | `2.1.177` |
| `cursor-cli` | Official shell installer (`https://cursor.com/install`) | Not version-pinned — supply-chain risk; prefer `copilot-cli` or `claude-code-cli` where pinning matters |

## GitHub Actions workflow inputs

The reusable workflow (`prevue-review.yml`) exposes these `workflow_call` inputs and secrets.

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `engine` | string | No | `copilot-cli` | Engine adapter name (`copilot-cli`, `claude-code-cli`, `cursor-cli`) |
| `model` | string | No | `""` | Review engine model override; equivalent to setting `PREVUE_MODEL`, takes precedence over `engine.model`/`engine.models.review` in `prevue.yml` |
| `config-path` | string | No | `.github/prevue.yml` | Path to `prevue.yml` relative to the consumer root (no `..`) |
| `prevue-ref` | string | No | `""` (→ `main`) | Prevue framework branch, tag, or SHA for self-checkout |
| `pr-head-sha` | string | No | `""` | PR head SHA; falls back to `github.event.pull_request.head.sha` |
| `consumer-base-sha` | string | No | `""` | PR base SHA; falls back to `github.event.pull_request.base.sha` |
| `seed-consumer-config` | boolean | No | `false` | When `true`, copies `.prevue/.github/prevue.yml` into the consumer checkout if absent (dogfood use only) |

### Secrets

| Secret | Required | Engine | Description |
|--------|----------|--------|-------------|
| `copilot-github-token` | No | `copilot-cli` | Fine-grained user PAT (`github_pat_…`) with Copilot Requests permission. Maps to `COPILOT_GITHUB_TOKEN` |
| `claude-code-oauth-token` | No | `claude-code-cli` | Long-lived OAuth token (`claude setup-token`). Maps to `CLAUDE_CODE_OAUTH_TOKEN` |
| `cursor-api-key` | No | `cursor-cli` | Cursor API key. Maps to `CURSOR_API_KEY` |
| `antigravity-api-key` | No | `antigravity-cli` | API key for `agy` (registered, not yet functional). Maps to `ANTIGRAVITY_API_KEY` |
| `gemini-api-key` | No | `antigravity-cli` | Documented alias for `antigravity-api-key`. Maps to `GEMINI_API_KEY` |

Pass only the secret for your chosen engine. Do **not** use `secrets: inherit`.

### Required permissions

| Permission | Scope | Why |
|------------|-------|-----|
| `contents` | `write` | Consumer base-ref checkout + GraphQL `resolveReviewThread` (LIFE-04). `read` returns 403 on thread resolve |
| `pull-requests` | `write` | Post review comments and sticky summary |
| `checks` | `write` | Create `prevue/review` pass/fail check run |

### Repository variables (optional)

Set these in the consumer repo's **Variables** settings (not secrets):

| Variable | Purpose |
|----------|---------|
| `PREVUE_ENGINE` | Override engine without editing the workflow YAML |
| `PREVUE_REF` | Prevue framework ref used by the command workflow (`prevue-command.yml`) |
| `PREVUE_STICKY_OWNER_LOGINS` | Comma-separated logins whose sticky comments are treated as trusted (for sticky comment ownership checks) |

## Environment overrides

Workflow/runtime variables that affect config resolution (not set in `prevue.yml`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PREVUE_CONSUMER_ROOT` | Recommended in Actions | — | Trusted base-ref checkout root; anchors config and consumer skill paths. Without this in Actions, consumer config is ignored (SKIL-04 fail-closed) |
| `PREVUE_CONFIG_PATH` | Optional | `.github/prevue.yml` | Config file path relative to consumer root; resolved and traversal-checked |
| `PREVUE_ENGINE` | Optional | `copilot-cli` | Overrides `engine.name` in `prevue.yml` |
| `PREVUE_MODEL` | Optional | — | Review engine model; `COPILOT_MODEL` is the Copilot adapter fallback |
| `COPILOT_MODEL` | Optional | — | Copilot-specific model override; superseded by `PREVUE_MODEL` if both set |
| `COPILOT_GITHUB_TOKEN` | Engine-dependent | — | Fine-grained PAT (`github_pat_…`) for `copilot-cli` |
| `CLAUDE_CODE_OAUTH_TOKEN` | Engine-dependent | — | OAuth token for `claude-code-cli` (`claude setup-token`) |
| `CURSOR_API_KEY` | Engine-dependent | — | API key for `cursor-cli` |

## Validation

Unknown keys in any section cause a load error (`extra: forbid` on all Pydantic config models). Additional validation:

- `review.output_reserve_tokens` > `review.max_input_tokens` → load error
- `review.max_tokens_per_call` > `review.max_total_run_tokens` → load error
- `review.output_reserve_tokens` > `review.max_tokens_per_call` → load error
- Invalid regex in `skip.skip_title_patterns` → load error
- Config path containing `..` → load error
- Config path escaping `PREVUE_CONSUMER_ROOT` (symlinks followed) → load error
- `skills.exclude` key matching no loaded skill → stderr warning, run continues

## Full example

Copy from [examples/prevue.yml](./examples/prevue.yml):

```yaml
# .github/prevue.yml — place on default branch; Prevue reads from PR base ref, not head.

ignore:
  - ".planning/**"
  - "docs/generated/**"

labels:
  security:
    - "**/auth/**"
    - "**/*secret*"
    - "**/.env*"

routing: {}

review:
  max_input_tokens: 120000
  output_reserve_tokens: 12000
  min_severity_to_comment: warning
  min_severity_to_fail: null
  max_inline_comments: 10
  incremental: true
  resolve_outdated: true
  max_known_issues: 20
  max_dismissals: 50
  # Multi-call caps (all optional; defaults preserve single-call behavior)
  max_review_calls: 1
  max_tokens_per_call: 120000
  max_total_run_tokens: 500000
  review_concurrency: 1
  guardrail_skills: []

skip:
  review_bots: []
  skip_labels:
    - skip-review
  skip_title_patterns: []

skills:
  exclude: []
  max_skill_bytes: 65536
  max_total_consumer_bytes: 262144
  max_consumer_skills: 50

classification:
  fallback:
    enabled: true
    model: null

engine:
  name: copilot-cli
```
