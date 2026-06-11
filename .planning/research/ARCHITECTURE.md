# Architecture Research

**Domain:** AI PR review framework delivered as a GitHub reusable workflow
**Researched:** 2026-06-12
**Confidence:** HIGH (GitHub mechanics from official docs) / MEDIUM (overall composition — synthesized from PR-Agent's proven architecture plus first-principles design for the skill-routing layer, which no existing tool implements)

## Standard Architecture

AI PR review systems converge on a layered pipeline: an entry point (Action/webhook/CLI) feeds an orchestrator, which drives tools through two abstraction seams — a **git provider seam** (fetch diff, post results) and an **AI model seam** (run the review). PR-Agent (the dominant open-source reference) is structured exactly this way: entry points → `PRAgent` orchestrator → tools → git-provider abstraction + AI-handler abstraction, with diff/token management as a dedicated subsystem. Prevue follows the same shape but replaces PR-Agent's "compress everything to fit" token strategy with classify→route→load selective skill loading, which is the project's differentiator.

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│ CONSUMER REPO                                                        │
│  .github/workflows/review.yml ──uses──> prevue reusable workflow     │
│  .github/prevue.yml (config)    .github/prevue/skills/ (custom)      │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │ workflow_call (inputs + secrets)
┌───────────────────────────────────▼──────────────────────────────────┐
│ PREVUE REUSABLE WORKFLOW (single job, thin YAML)                     │
│  checkout prevue @ job.workflow_sha → setup python → run CLI         │
├──────────────────────────────────────────────────────────────────────┤
│ PREVUE PYTHON PIPELINE (one process, staged, artifacts on disk)      │
│                                                                      │
│  ┌──────────┐   ┌────────────┐   ┌────────┐   ┌─────────────┐        │
│  │   Diff   │──▶│ Classifier │──▶│ Router │──▶│ Skill Loader│        │
│  │ Fetcher  │   │ (hybrid)   │   │        │   │ + Resolver  │        │
│  └──────────┘   └────────────┘   └────────┘   └──────┬──────┘        │
│   DiffBundle    Classification    RoutingPlan        │ ReviewContext │
│                                                      ▼               │
│  ┌─────────────┐    ReviewResult    ┌────────────────────────┐       │
│  │   Output    │◀───────────────────│  Engine Adapter (ABC)  │       │
│  │   Writer    │                    │  └─ CopilotCliAdapter  │       │
│  └──────┬──────┘                    └───────────┬────────────┘       │
└─────────┼───────────────────────────────────────┼────────────────────┘
          │ GITHUB_TOKEN                          │ COPILOT_GITHUB_TOKEN
          ▼                                       ▼
   GitHub REST API                         copilot -p ... -s
   (Reviews, Issues,                       --no-ask-user
    job exit code = check)                 (subprocess)
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Reusable workflow (`.github/workflows/review.yml`) | Entry point. Declares `workflow_call` inputs/secrets, checks out prevue's own code via `job.workflow_repository`/`job.workflow_sha`, checks out consumer repo, installs Python, invokes the CLI. **Contains no logic.** | ~50 lines of YAML; every behavior lives in Python so it's testable locally |
| Config loader | Merge defaults ← workflow inputs ← consumer `.github/prevue.yml` into one frozen `PrevueConfig` object handed to every stage | `pydantic` model; single place that touches env vars/inputs |
| Diff fetcher | Pull PR metadata, changed-file list, and per-file patches via GitHub API; emit `DiffBundle`. Owns size truncation policy (per-file and total caps) | `GET /pulls/{n}/files` (paginated) + `GET /pulls/{n}` ; no git clone needed for the diff itself |
| Classifier (hybrid) | Deterministic pass: glob/path/extension/lockfile rules over `DiffBundle.files` → labels with confidence. LLM fallback **only** for files/PRs no rule matches | Rules engine in pure Python (zero tokens); fallback is one small prompt through the engine adapter's `classify()` hook |
| Router | Map labels → skill bundle IDs; resolve precedence (consumer override > consumer custom > built-in); emit `RoutingPlan` | Static label→bundle table + config-driven additions; pure function, trivially unit-testable |
| Skill loader / resolver | Read SKILL.md files for routed bundles only; merge built-in (`skills/` in prevue checkout) with consumer (`.github/prevue/skills/`); assemble `ReviewContext` | Filesystem reads; bundles follow the Agent Skills SKILL.md convention (YAML frontmatter + markdown body) |
| Engine adapter (interface) | `review(ReviewContext) -> ReviewResult` and optional `classify(snippet) -> labels`. Owns prompt assembly for its engine and parsing engine output into the structured result | Python `ABC`/`Protocol`; registry keyed by engine name from config |
| CopilotCliAdapter | First concrete adapter: writes assembled prompt to file, runs `copilot -p "$(cat prompt.md)" -s --no-ask-user --allow-tool='shell(cat),read'`, parses fenced-JSON response | `subprocess.run`; auth via `COPILOT_GITHUB_TOKEN` env; model via `COPILOT_MODEL` |
| Output writer | Validate `ReviewResult` findings against the diff (line exists in patch?), post one review via Reviews API (summary body + inline `comments[]` with `path`/`line`/`side`), set pass/fail | `POST /pulls/{n}/reviews` with `event: COMMENT`; gate = process exit code → job status (the workflow run **is** the required check) |
| Stage artifact store | Each stage writes its output JSON to `$RUNNER_TEMP/prevue/` (`diff.json`, `classification.json`, `routing.json`, `review.json`) and uploads on failure | Plain JSON files; enables `--from-stage` local replay and debugging failed runs |

## Recommended Project Structure

```
prevue/                          # repo root
├── .github/
│   └── workflows/
│       ├── review.yml           # THE reusable workflow (workflow_call)
│       └── ci.yml               # prevue's own tests
├── src/prevue/                  # Python package
│   ├── models.py                # DiffBundle, Classification, RoutingPlan,
│   │                            #   ReviewContext, ReviewResult (pydantic)
│   ├── config.py                # PrevueConfig: defaults+inputs+prevue.yml merge
│   ├── github/
│   │   ├── client.py            # thin REST wrapper (auth, pagination, retries)
│   │   └── diff.py              # diff fetcher → DiffBundle
│   ├── classify/
│   │   ├── rules.py             # deterministic glob/path/pattern rules
│   │   ├── default_rules.yml    # built-in rule table (data, not code)
│   │   └── llm_fallback.py      # ambiguity detection + small-LLM call
│   ├── route/
│   │   └── router.py            # labels → bundles, precedence resolution
│   ├── skills/
│   │   ├── loader.py            # SKILL.md parsing, bundle discovery
│   │   └── resolver.py          # built-in vs consumer merge/override
│   ├── engines/
│   │   ├── base.py              # EngineAdapter ABC + registry
│   │   ├── copilot_cli.py       # first adapter
│   │   └── prompts/             # prompt templates (jinja2), incl. JSON
│   │                            #   output-schema instructions
│   ├── output/
│   │   ├── validator.py         # finding↔diff line validation, degradation
│   │   └── writer.py            # Reviews API post, summary, exit code
│   └── cli.py                   # `prevue review`, `prevue classify`, ...
├── skills/                      # BUILT-IN bundles (data, ships with repo)
│   ├── security/
│   │   ├── SKILL.md             # bundle root: scope + routing description
│   │   └── *.md                 # individual guideline files
│   ├── frontend/ … backend/ … data/ … infra/
├── tests/
│   ├── fixtures/                # recorded DiffBundles, golden outputs
│   └── ...
├── pyproject.toml
└── README.md
```

### Structure Rationale

- **`src/prevue/` mirrors the pipeline stages 1:1.** Each stage is a package with one public function consuming/producing the models in `models.py`. Phase boundaries in the roadmap can map directly onto these packages.
- **`skills/` at repo root, outside the package:** skills are content, not code. They're read from the prevue checkout at runtime (available because the workflow checks out its own repo) and can be edited by non-Python contributors without touching the package.
- **`classify/default_rules.yml` as data:** the deterministic rule table will churn far more than the rule engine; keeping it declarative lets consumers extend it via `prevue.yml` with the same syntax.
- **`engines/prompts/` colocated with adapters:** prompt assembly is adapter-owned (different engines want different framing), but templates are shared raw material.
- **`cli.py` exposing every stage:** `prevue classify --diff diff.json` etc. makes the whole pipeline runnable/debuggable locally without GitHub Actions — critical for development velocity since Actions iteration loops are slow.

## Architectural Patterns

### Pattern 1: Thin workflow, fat CLI

**What:** The reusable workflow YAML does only environment setup (checkouts, Python, `pip install`) and one `prevue review` invocation. All logic — including reading `GITHUB_EVENT_PATH` for PR context — lives in Python.
**When to use:** Always, for anything delivered as a workflow/action with non-trivial logic.
**Trade-offs:** Slightly more bootstrap (must check out prevue's own repo). In exchange: unit-testable logic, local reproduction (`prevue review --pr 123 --repo o/r`), and no YAML-embedded bash to debug. PR-Agent's `github_action_runner.py` follows the same principle.

**Example:**
```yaml
# .github/workflows/review.yml (the reusable workflow)
on:
  workflow_call:
    inputs:
      config-path: { type: string, default: ".github/prevue.yml" }
      engine:      { type: string, default: "copilot-cli" }
      fail-on:     { type: string, default: "error" }   # none|error|warning
    secrets:
      COPILOT_GITHUB_TOKEN: { required: true }
jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      # Critical: default checkout would fetch the CALLER's repo.
      - uses: actions/checkout@v4
        with:
          repository: ${{ job.workflow_repository }}
          ref: ${{ job.workflow_sha }}
          path: prevue
      - uses: actions/checkout@v4
        with: { path: consumer }    # consumer repo: prevue.yml + custom skills
      - run: pip install ./prevue
      - run: prevue review
        env:
          GITHUB_TOKEN: ${{ github.token }}
          COPILOT_GITHUB_TOKEN: ${{ secrets.COPILOT_GITHUB_TOKEN }}
          PREVUE_CONFIG: consumer/${{ inputs.config-path }}
```

### Pattern 2: Pipeline with typed JSON artifacts between stages

**What:** Each stage is a pure-ish function over pydantic models; the orchestrator serializes each stage's output to `$RUNNER_TEMP/prevue/*.json`. Stages never reach around each other — the router never sees the raw diff, the engine never sees routing internals.

The artifact contracts (this is the core data flow design):

```
DiffBundle        { pr: {number, title, body, base_sha, head_sha, author},
                    files: [{path, status, additions, deletions, patch,
                             truncated: bool}],
                    total_changes, truncation_applied }
Classification    { labels: [{name, confidence, source: "rule"|"llm",
                              matched_files: [...]}],
                    unmatched_files: [...], llm_calls_made: int }
RoutingPlan       { bundles: [{id, origin: "builtin"|"consumer"|"override",
                               path, reason: "label:security"}],
                    skipped_labels: [...] }
ReviewContext     { diff: DiffBundle, skills: [{bundle_id, name, content}],
                    instructions: str, output_schema: str, budget_tokens }
ReviewResult      { summary_markdown: str,
                    findings: [{path, line, side, end_line?, severity:
                                "error"|"warning"|"info", title, body,
                                suggestion?}],
                    verdict: "pass"|"fail", engine_meta: {model, duration} }
```

**When to use:** Any multi-stage system where stages may later be re-run independently, swapped (engines), or debugged from a failed CI run.
**Trade-offs:** Serialization ceremony vs. enormous debuggability win: a failed review run uploads its artifacts, and `prevue review --from-stage route` replays locally from `routing.json`.

### Pattern 3: Ports-and-adapters engine seam, with the output writer outside it

**What:** `EngineAdapter` is the only component that knows any AI vendor exists. Crucially, the adapter returns a `ReviewResult`; it does **not** post to GitHub. The engine is denied write access to the GitHub API entirely (Copilot CLI gets minimal `--allow-tool` grants — read-only file access at most).

```python
class EngineAdapter(ABC):
    name: str
    @abstractmethod
    def review(self, ctx: ReviewContext) -> ReviewResult: ...
    def classify(self, prompt: str) -> list[str]:
        raise UnsupportedCapability  # optional hook for LLM-fallback classifier

# engines/copilot_cli.py
class CopilotCliAdapter(EngineAdapter):
    name = "copilot-cli"
    def review(self, ctx: ReviewContext) -> ReviewResult:
        prompt_path = self._write_prompt(ctx)          # skills + diff + schema
        out = subprocess.run(
            ["copilot", "-p", f"Follow the review instructions in {prompt_path}",
             "-s", "--no-ask-user", f"--allow-tool=read"],
            env={**os.environ, "COPILOT_GITHUB_TOKEN": self.token},
            capture_output=True, text=True, timeout=ctx.budget_seconds)
        return self._parse_result(out.stdout)          # fenced JSON → ReviewResult
```

**When to use:** From day one — it is a stated project constraint, and retrofitting it after Copilot-specific behavior leaks into the pipeline is a rewrite.
**Trade-offs:** Structured-output parsing is the weak joint: CLI agents emit prose around JSON. Mitigate with (a) explicit JSON-schema instructions in the prompt, (b) tolerant extraction (find last fenced JSON block), (c) one retry with a "respond with only JSON" nudge, (d) hard fallback to summary-only output (post the raw text as the summary comment, no inline comments, neutral verdict).

### Pattern 4: Prompt assembly as the canonical skill-injection mechanism

**What:** The skill loader produces engine-neutral text (`ReviewContext.skills[].content`); each adapter assembles it into its prompt file. **Do not** rely on an engine's native skill discovery (Copilot CLI's `AGENTS.md` / `COPILOT_CUSTOM_INSTRUCTIONS_DIRS` / `.github/copilot-instructions.md`) as the primary mechanism.

Why: native loading (1) is per-engine and would couple the loader to each adapter's conventions, defeating pluggability; (2) is *discovery-based* — the engine decides what to load, which surrenders Prevue's core value (the pipeline already decided exactly which skills apply; re-delegating that decision to the engine reintroduces nondeterminism and token waste); (3) risks double-loading when the consumer repo also has its own `AGENTS.md` (Copilot CLI auto-reads the cwd's instruction files — run the CLI from a clean working directory, not the consumer checkout, or accept the consumer's repo instructions deliberately).

Native loading remains available as an adapter-private optimization (e.g. the Copilot adapter *may* write skills to a temp dir and set `COPILOT_CUSTOM_INSTRUCTIONS_DIRS`), but the contract stays "adapter receives resolved skill text."

**When to use:** Whenever the orchestrating system, not the agent, owns context selection.
**Trade-offs:** Loses engine-native progressive disclosure (level-3 resource files inside a skill bundle won't be lazily fetched). Acceptable: routed bundles are already scoped small; cap assembled skill text and let the bundle's SKILL.md be the budget unit.

### Pattern 5: Chain-of-responsibility hybrid classifier

**What:** Ordered rule passes — (1) exact-path rules (lockfiles, `Dockerfile`, `.github/workflows/`), (2) glob/extension rules, (3) content-pattern rules on patch text (e.g. `password|secret` hits security) — each tagging files with labels. Only files left unlabeled, or PRs whose label set is empty/contradictory, go to the LLM fallback with a *minimal* payload (file paths + hunk headers, not full patches).
**When to use:** Whenever cost requires deterministic-first. The same pattern is why the classifier must emit `Classification.llm_calls_made` — it's the metric proving the zero-token promise.
**Trade-offs:** Rule tables need maintenance; mitigate by shipping them as data (`default_rules.yml`) and letting consumers extend via `prevue.yml` rather than forking.

## Data Flow

### Request Flow

```
PR event (caller repo)
    ↓ workflow_call (inputs + secrets explicit, never `secrets: inherit` advice)
Reusable workflow job
    ↓ checkout prevue@workflow_sha + consumer repo; pip install; prevue review
Diff Fetcher ──GET /pulls/{n}, /pulls/{n}/files──▶ DiffBundle ──▶ diff.json
    ↓
Classifier (rules) ──[only ambiguous]──▶ EngineAdapter.classify()
    ↓ Classification ──▶ classification.json
Router (+ PrevueConfig: consumer bundle map, overrides)
    ↓ RoutingPlan ──▶ routing.json
Skill Loader (reads prevue/skills/* and consumer/.github/prevue/skills/*)
    ↓ ReviewContext (skills + diff + instructions + output schema)
EngineAdapter.review() ──subprocess: copilot -p … -s --no-ask-user──▶
    ↓ ReviewResult ──▶ review.json
Output Validator (drop/degrade findings whose path:line isn't in the diff)
    ↓
Output Writer ──POST /pulls/{n}/reviews (body=summary, comments=findings,
               event=COMMENT)──▶ GitHub
    ↓
exit code 0/1 per verdict×fail-on  ──▶  job status = the pass/fail check
```

### Key Data Flows

1. **Diff → labels (forward-only):** classification consumes file metadata first, patch content only for pattern rules and LLM fallback. Nothing downstream mutates the `DiffBundle`; it's passed by reference into `ReviewContext` so the engine reviews exactly what was classified.
2. **Config fan-in:** `PrevueConfig` is built once (defaults ← workflow inputs ← consumer `prevue.yml`) and injected into classifier (extra rules), router (bundle mappings, disabled bundles), loader (custom skill dir), engine selection, and output (fail-on threshold). Consumers therefore have two knobs and only two: workflow `with:` inputs for run-shape (engine, fail-on, config path) and `prevue.yml` for review-shape (rules, bundles, skills).
3. **Findings → posts (validated):** `ReviewResult.findings[].line` refers to head-revision line numbers; the validator checks each against the fetched patch hunks before posting (use `line`/`side` params, never legacy `position`). Invalid findings degrade to the summary section ("possibly stale: …") rather than being silently dropped.
4. **Pass/fail via job status, not Checks API:** the Checks API's rich features require a GitHub App; from a workflow, the job's own success/failure already surfaces as a required-check candidate in branch protection. v1 gate = exit code. (A `statuses: write` commit status is an optional later refinement; a full Checks-API annotation writer only makes sense if Prevue ever ships as a GitHub App.)

### State Management

Stateless per run. The only persistence is stage artifacts in `$RUNNER_TEMP` (debugging) and an idempotency marker: the output writer tags its review comment with a hidden HTML marker (`<!-- prevue:run -->`) so re-runs on `synchronize` can update/supersede the previous summary comment instead of stacking duplicates.

## Delivery Mechanism: Reusable Workflow vs Composite Action vs Docker Action

| Criterion | Reusable workflow (chosen) | Composite action | Docker action |
|-----------|---------------------------|------------------|---------------|
| Unit of reuse | Whole job (runner, permissions, steps) | Step bundle inside caller's job | Single step, own container |
| Permissions | Declares its own `permissions:` block — consumer sees exactly what it requests | Inherits caller job's permissions implicitly | Inherits caller job's permissions |
| Consumer YAML | ~10 lines: one job with `uses:` + `with:` + `secrets:` | Caller must own checkout, Python setup, step wiring | Caller owns job; container startup cost per run |
| Own-code access | Must self-checkout via `job.workflow_repository`/`job.workflow_sha` (not available on GHES — known limitation) | Action repo files come along automatically | Code baked into image |
| Secrets | Explicit `secrets:` declaration (auditable) | Ambient env | Ambient env |
| Versioning | `@v1` tag / SHA pin on the `uses:` line | Same | Image tag + action ref |

**Decision:** reusable workflow, as constrained by the project. It fits: the unit of reuse genuinely is a job (own permissions, own runner, complete pipeline), and the explicit `permissions:`/`secrets:` declarations directly serve the "consumers must be able to trust it" constraint. The standard rule of thumb ("reusable workflow when the unit is a job; composite action when it's steps inside an existing job") confirms this. A composite action wrapper can be added later for consumers who want Prevue as a step inside an existing job — the thin-workflow/fat-CLI split makes that nearly free.

## Anti-Patterns

### Anti-Pattern 1: Letting the engine post to GitHub

**What people do:** Grant the CLI agent `--allow-tool='shell(gh:*)'` or write access and prompt it to "post review comments."
**Why it's wrong:** Blows up the minimal-permissions trust story; output becomes unvalidated and non-deterministic (duplicate comments, wrong line anchors); behavior diverges per engine, breaking adapter symmetry.
**Do this instead:** Engine returns structured `ReviewResult`; the output writer — deterministic, tested Python — owns every GitHub write.

### Anti-Pattern 2: Logic in workflow YAML

**What people do:** Inline bash for diff fetching, jq-parsing event payloads, conditionals across steps.
**Why it's wrong:** Untestable, undebuggable locally, and every fix needs a tagged release consumers must bump.
**Do this instead:** Thin workflow, fat CLI (Pattern 1).

### Anti-Pattern 3: Default checkout in a reusable workflow

**What people do:** Plain `actions/checkout@v4`, assuming it fetches the workflow's own repo.
**Why it's wrong:** Reusable workflows run in the *caller's* context — default checkout fetches the consumer repo, and the framework's Python/skills are silently absent.
**Do this instead:** Checkout `${{ job.workflow_repository }}` at `${{ job.workflow_sha }}` for prevue code; second checkout for the consumer repo (config + custom skills).

### Anti-Pattern 4: Skill auto-discovery by the engine

**What people do:** Drop all skill bundles where the engine's native instruction loading finds them (consumer `AGENTS.md`, instructions dirs) and let the model pick.
**Why it's wrong:** Re-delegates the selection decision the classifier/router already made deterministically; token usage becomes engine-dependent; pluggability dies because every engine discovers differently.
**Do this instead:** Pattern 4 — pipeline-owned prompt assembly; native loading only as adapter-internal optimization.

### Anti-Pattern 5: Trusting LLM line numbers

**What people do:** Post `findings[].line` straight to the Reviews API.
**Why it's wrong:** Models hallucinate line numbers and reference unchanged lines; the API 422s when a comment targets a line outside the diff, failing the whole review post.
**Do this instead:** Validate every finding against fetched patch hunks; degrade invalid ones into the summary body; post the review even if some findings are dropped.

### Anti-Pattern 6: `pull_request_target` for convenience

**What people do:** Trigger on `pull_request_target` to get a write-token on fork PRs, while checking out and processing untrusted fork code/diff content into prompts.
**Why it's wrong:** Classic privilege-escalation vector — untrusted diff content reaches a privileged context (and prompt-injection via PR content is this system's specific variant).
**Do this instead:** v1: `pull_request` trigger, same-repo PRs (fork PRs get read-only behavior or are skipped). Treat diff text as untrusted input in prompt templates (delimit it, instruct the engine to ignore instructions inside it).

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| GitHub REST — PR data | `GET /pulls/{n}`, `GET /pulls/{n}/files` (paginated, `patch` per file) | 3000-file cap and per-patch size limits; `DiffBundle.truncated` must be first-class, not an afterthought |
| GitHub REST — Reviews | `POST /pulls/{n}/reviews` with `event: COMMENT`, `body` = summary, `comments[]` = `{path, line, side, body}` | One API call posts summary + all inline comments atomically — strongly preferred over N single-comment calls (rate limits, notification spam) |
| Pass/fail gate | Process exit code → job conclusion; consumers mark the job as a required check | Checks API rich annotations are GitHub-App-only; do not design around them for v1 |
| Copilot CLI | `subprocess`: `copilot -p … -s --no-ask-user --allow-tool=…`; auth `COPILOT_GITHUB_TOKEN` (PAT of a Copilot-licensed user); model via `COPILOT_MODEL` | Must be installed on the runner (npm install step in the workflow); `-s` gives clean stdout for parsing; enforce `timeout` |
| Consumer repo | Second checkout: `.github/prevue.yml` + `.github/prevue/skills/**/SKILL.md` | Read-only; absence of both = pure defaults, which must be a fully working zero-config path |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Workflow ↔ CLI | argv + env (`GITHUB_TOKEN`, `COPILOT_GITHUB_TOKEN`, `PREVUE_CONFIG`, `GITHUB_EVENT_PATH`) | The only place env vars are read; everything below gets `PrevueConfig` |
| Stage ↔ stage | Typed pydantic models in-process; JSON artifacts on disk as side-channel | Models are the contract; artifacts are for replay/debug only |
| Pipeline ↔ engine | `EngineAdapter.review(ReviewContext) -> ReviewResult` | The pluggability seam; nothing above it imports engine modules directly (registry + config-driven selection) |
| Loader ↔ skill content | SKILL.md convention (frontmatter `name`/`description` + markdown body) | Same format for built-in and consumer skills → override = same-name shadowing, no special cases |
| Pipeline ↔ GitHub | Single `github/client.py` wrapper | One place for auth, retries, rate-limit handling, and API-version pinning |

## Suggested Build Order

Dependencies run mostly forward along the pipeline; the engine adapter is the riskiest external integration and should be de-risked before the layers that depend on its output shape are polished.

1. **Models + config + GitHub client + diff fetcher** — `models.py` is the contract everything else codes against; the diff fetcher makes the system observable end-to-end (`prevue fetch --pr N` prints a DiffBundle). No AI, no workflow yet. *Everything depends on this.*
2. **Deterministic classifier + router + default rule table** — pure functions over DiffBundle; fully unit-testable with fixture diffs; proves the zero-token path. *Depends on 1 only.*
3. **Skill loader + built-in bundles (initial security/backend content)** — establishes SKILL.md conventions and ReviewContext assembly. Bundle *content* can be thin; the loading/resolution machinery is what matters here. *Depends on 2 (consumes RoutingPlan).*
4. **Engine adapter interface + Copilot CLI adapter (spike early)** — highest integration risk: auth in Actions, output parsing, timeouts. Worth a thin walking-skeleton spike during phase 1–2 to validate `copilot -p` behaves on a runner; full adapter lands here. *Depends on 3 (consumes ReviewContext); blocks 5 and 6.*
5. **Output validator + writer** — Reviews API post, finding validation/degradation, idempotency marker, exit-code gate. *Depends on 4's ReviewResult shape.*
6. **Reusable workflow + consumer config surface + LLM-fallback classifier** — wire the thin YAML (self-checkout, dual checkout, install, invoke); `prevue.yml` parsing; the LLM fallback slots in here because it reuses the engine adapter from 4. End of this phase = first real PR reviewed end-to-end from a consumer repo. *Depends on 1–5.*
7. **Consumer custom skills + overrides + remaining built-in bundles (frontend/data/infra) + hardening** — override precedence, bundle content depth, fork-PR posture, prompt-injection delimiting, large-PR truncation tuning. *Depends on 6 (needs the consumer checkout path live).*

Rationale highlights for the roadmap:
- **1→2→3 are pure-Python, fast phases** with no external risk; they build the artifact spine.
- **4 is the research-flagged phase** (Copilot CLI behavior on runners, structured output reliability) — schedule the spike early even though full integration lands mid-roadmap.
- **6 is the first shippable milestone** (zero-config consumer can adopt); 7 is the "framework, not tool" milestone (customization surface).

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single team, few repos | Everything above as-is; job-status gate; built-in bundles only |
| Org-wide (50+ repos) | Version discipline on the `@v1` tag; org-level `prevue.yml` defaults (workflow input pointing at a shared config repo is a cheap v2); watch Copilot CLI per-user PAT quotas — a dedicated bot user with a Copilot seat |
| Large PRs / monorepos | First bottleneck is context size, not throughput: per-bundle token budgets in ReviewContext, file-relevance ranking before truncation (PR-Agent's compression strategy is the reference), optionally one engine call per routed bundle and merge results |

**First bottleneck:** assembled prompt size on big PRs → enforce `ReviewContext.budget_tokens` with ranked truncation from day one (cheap now, painful later).
**Second bottleneck:** review latency per PR (single sequential engine call) → per-bundle parallel engine calls, merged by the output writer; the artifact design already permits this since `ReviewResult`s are mergeable.

## Sources

- [PR-Agent system architecture (DeepWiki)](https://deepwiki.com/qodo-ai/pr-agent/1.1-system-architecture) — layered entry-points/orchestrator/tools/provider-seam reference — MEDIUM
- [PR-Agent diff processing & token management (DeepWiki)](https://deepwiki.com/qodo-ai/pr-agent/3.4-diff-processing-and-token-management) — compression strategy reference for large PRs — MEDIUM
- [GitHub Docs: Reusing workflow configurations](https://github.com/github/docs/blob/main/content/actions/concepts/workflows-and-actions/reusing-workflow-configurations.md) — reusable workflow vs composite action semantics — HIGH
- [GitHub Docs: Contexts reference (`job.workflow_repository`/`job.workflow_sha`)](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts) — self-checkout pattern; GHES limitation — HIGH
- [actions/checkout#1418](https://github.com/actions/checkout/issues/1418) — the default-checkout-in-reusable-workflow failure mode — HIGH
- [GitHub Docs: Run Copilot CLI programmatically](https://github.com/github/docs/blob/main/content/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically.md) — `-p`/`-s`/`--no-ask-user`/`--allow-tool`, Actions example with `COPILOT_GITHUB_TOKEN` — HIGH
- [GitHub Docs: Copilot CLI custom instructions](https://github.com/github/docs/blob/main/content/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions.md) — `AGENTS.md`, `COPILOT_CUSTOM_INSTRUCTIONS_DIRS`, precedence — HIGH
- [GitHub Docs: Pull request reviews REST API](https://docs.github.com/rest/pulls/reviews) — single-call review with `comments[]` (`path`/`line`/`side`) — HIGH
- [GitHub Docs: Using the REST API to interact with checks](https://github.com/github/docs/blob/main/content/rest/guides/using-the-rest-api-to-interact-with-checks.md) — Checks API is GitHub-Apps-only — HIGH
- [Agent Skills specification](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx) — SKILL.md format, progressive disclosure model — HIGH
- [Reusable workflows vs composite actions enterprise patterns (Opsio)](https://opsiocloud.com/blogs/reusable-workflows-composite-actions-enterprise-patterns/) — job-vs-steps decision rule, `secrets: inherit` blast radius — MEDIUM

---
*Architecture research for: AI PR review framework as GitHub reusable workflow*
*Researched: 2026-06-12*
