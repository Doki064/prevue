<!-- generated-by: gsd-doc-writer -->
# Configuration

Consumer settings live in `.github/prevue.yml` on the **trusted base ref** (default branch at review time — not the PR head). Prevue reads the file once per run via `load_config()` and validates every section with Pydantic (`extra: forbid` — unknown keys fail at load).

If the file is missing, framework defaults apply (including `classification.fallback.enabled: true`). A stderr notice is emitted so silent LLM classify calls are not a surprise.

**Custom workflow integrators:** set `PREVUE_CONSUMER_ROOT` to a checkout of the base ref. Without it in GitHub Actions, consumer config is ignored (SKIL-04 fail-closed). See [consumer-setup.md](./consumer-setup.md).

## Quick reference

| Section | Purpose |
|---------|---------|
| `ignore` | Drop paths from the diff before classification |
| `labels` | Map file globs → classification labels (pack priority + skill routing input) |
| `routing` | Map labels → skill bundle ids |
| `review` | Token budget, severity thresholds, inline cap, incremental lifecycle |
| `skip` | Skip review for bots, labels, or title regexes |
| `skills` | Consumer skill caps and exclusions |
| `classification.fallback` | LLM classify for unmatched paths |
| `engine` | Review engine adapter name |

Override config path with `PREVUE_CONFIG_PATH` (default `.github/prevue.yml`), resolved under `PREVUE_CONSUMER_ROOT` with traversal rejected.

## `ignore`

Additive gitignore-style globs merged **on top of** built-in noise filters (lockfiles, minified assets, `dist/`, binaries, etc. in `prevue/classify/default_rules.yml`).

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

Per-label glob lists. Consumer entries **replace** that label's built-in globs (not merged). Used for deterministic classification, pack priority, and (indirectly) skill bundle selection.

Built-in labels (from packaged rules): `security`, `frontend`, `backend`, `data`, `infra`. Unmatched paths become `general`.

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

**Pack priority:** lower canonical rank wins (`security` before `frontend` before `general`). Files with no label match get lowest priority and are dropped first when over `review.max_input_tokens`.

**Limitation — LLM-only paths under tight budgets:** Pack priority is computed from `labels` globs and skill `applies-to` *before* the LLM classification fallback runs. A file that no deterministic glob matches gets the lowest pack priority and is dropped first when over budget — so the LLM fallback (which might have flagged it security-relevant) never sees it. Under tight `max_input_tokens`, unrule-matched high-risk files can be silently excluded. Mitigation: add explicit `labels` globs for security-sensitive path patterns (e.g. `**/auth/**`, `**/*secret*`) so they pack ahead of generic files, or raise the budget.

## `routing`

Maps classification labels to skill **bundle** directory names. Default: each label routes to a bundle of the same name (`routing: {}`).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `routing.<label>` | string (bundle id) | `<label>` | Bundle loaded from `.github/prevue/skills/<bundle>/` (plus built-ins) |

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
| `max_input_tokens` | int (1–250000) | `120000` | Total prompt token budget (~bytes/4 heuristic). Diff packing target before engine invoke |
| `output_reserve_tokens` | int (≥0) | `12000` | Tokens reserved for engine JSON output; must be ≤ `max_input_tokens` |
| `min_severity_to_comment` | `error` \| `warning` \| `info` | `warning` | Minimum severity posted as inline or summary comment |
| `min_severity_to_fail` | `error` \| `warning` \| `info` \| null | `null` | Check conclusion `failure` when any finding meets this severity; `null` = never fail (neutral only) |
| `max_inline_comments` | int (≥0) | `10` | Cap on inline review comments; overflow goes to summary |
| `incremental` | bool | `true` | After first review, subsequent pushes review only the delta since the last sticky marker SHA |
| `resolve_outdated` | bool | `true` | Auto-resolve prior inline threads whose line regions no longer overlap the incremental diff |
| `max_known_issues` | int (≥0) | `20` | Prior open findings injected into the prompt as known issues (dedupe guidance) |
| `max_dismissals` | int (≥0) | `50` | Cap on persisted `/prevue dismiss` entries in the sticky comment |

```yaml
review:
  max_input_tokens: 120000
  output_reserve_tokens: 12000
  min_severity_to_comment: warning
  min_severity_to_fail: error
  max_inline_comments: 10
  incremental: true
  resolve_outdated: true
  max_known_issues: 20
  max_dismissals: 50
```

### Review budget behavior

Effective diff budget = `max_input_tokens` minus prompt overhead (skills, instructions, known-issues block). `max_input_tokens` default stays under the ~250k-token stdin guard (`MAX_PROMPT_BYTES` = 1_000_000 bytes ÷ 4 in `src/prevue/engines/prompt.py`). Oversized PRs pack whole files by risk weight; skipped files are disclosed in the summary.

`min_severity_to_fail` is independent of `min_severity_to_comment` — fail evaluates **all** findings regardless of comment threshold.

`/prevue review` forces a full re-review regardless of `incremental`. Same-SHA re-runs are a no-op even when `incremental: false`.

## `skip`

Skip policy evaluated before engine spend (`SkipConfig` in `src/prevue/config.py`).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `review_bots` | list of logins | `[]` | **Allowlist** of bot logins to review; any other `Bot` author skips the run |
| `skip_labels` | list of strings | `["skip-review"]` | PR labels that skip review |
| `skip_title_patterns` | list of regex strings | `[]` | PR title patterns that skip review (validated at config load) |

```yaml
skip:
  review_bots:
    - release-please[bot]
  skip_labels:
    - skip-review
    - wip
  skip_title_patterns:
    - "^\\[skip prevue\\]"
    - "^WIP:"
```

Empty `review_bots` means **all** bot-authored PRs are skipped.

## `skills`

Consumer skill overrides under `.github/prevue/skills/` (`SkillsConfig`). See [skills.md](./skills.md).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `exclude` | list of `bundle/filename.md` | `[]` | Exact skill keys to disable (not globs) |
| `max_skill_bytes` | int (≥1) | `65536` | Per-skill body cap (64 KiB) |
| `max_total_consumer_bytes` | int (≥1) | `262144` | Aggregate consumer skill body cap (256 KiB) |
| `max_consumer_skills` | int (≥1) | `50` | Max consumer skill files loaded per PR |

```yaml
skills:
  exclude:
    - security/committed-secrets.md
  max_skill_bytes: 65536
  max_total_consumer_bytes: 262144
  max_consumer_skills: 50
```

Over-cap or excluded skills are skipped and disclosed; malformed skills fail the run.

## `classification.fallback`

Hybrid LLM classify for paths with no deterministic label match (`FallbackConfig`).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `classification.fallback.enabled` | bool | `true` | Run LLM classify on unmatched paths in the **packed (reviewed)** file set |
| `classification.fallback.model` | string \| null | `null` | Model passed to the engine adapter for classify; `null` uses `PREVUE_MODEL` or `COPILOT_MODEL` from the workflow environment |

```yaml
classification:
  fallback:
    enabled: true
    model: null
```

When disabled or unavailable, unmatched paths stay `general`. LLM classify never runs on files dropped by `ignore` or pack budget.

## `engine`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `engine.name` | string | `copilot-cli` | Registered adapter name |

```yaml
engine:
  name: copilot-cli
```

**Precedence:** `PREVUE_ENGINE` environment variable overrides `engine.name`; both override the framework default (`copilot-cli`).

| Engine name | Status |
|-------------|--------|
| `copilot-cli` | Functional (default) |
| `claude-code-cli` | Functional |
| `cursor-cli` | Functional |
| `gemini-cli` | Registered skeleton — not yet functional for review |

Review model (separate from classify fallback model): set `PREVUE_MODEL` or `COPILOT_MODEL` in the workflow environment.

## Environment overrides

Workflow/runtime variables that affect config resolution (not set in `prevue.yml`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PREVUE_CONSUMER_ROOT` | Recommended in Actions | — | Trusted base-ref checkout root; anchors config and skill paths |
| `PREVUE_CONFIG_PATH` | Optional | `.github/prevue.yml` | Config file path relative to consumer root |
| `PREVUE_ENGINE` | Optional | `copilot-cli` | Overrides `engine.name` |
| `PREVUE_MODEL` | Optional | — | Review engine model |
| `COPILOT_MODEL` | Optional | — | Fallback when `PREVUE_MODEL` unset (Copilot adapter) |

## Validation

- Unknown keys in any section → load error (`extra: forbid` on all Pydantic config models).
- `review.output_reserve_tokens` > `review.max_input_tokens` → load error.
- Invalid regex in `skip.skip_title_patterns` → load error.
- Config path containing `..` or escaping `PREVUE_CONSUMER_ROOT` → load error.

## Full example

Copy from [examples/prevue.yml](./examples/prevue.yml):

```yaml
# .github/prevue.yml on default branch

ignore:
  - "docs/generated/**"

labels:
  security:
    - "**/auth/**"
    - "**/*secret*"

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
