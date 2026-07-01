---
status: diagnosed
phase: 10-boundary-contracts
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md, 10-04-SUMMARY.md, 10-05-SUMMARY.md, 10-06-SUMMARY.md, 10-07-SUMMARY.md]
started: 2026-07-01T09:51:21Z
updated: 2026-07-01T11:05:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Real token accounting + cost line on sticky comment
expected: |
  Run a review with an engine that captures real token usage (e.g. claude-code-cli
  stdout-json envelope, or copilot-cli with COPILOT_OTEL_FILE_EXPORTER_PATH wired).
  The sticky PR comment's Tokens line shows real (non-estimated) counts with no
  "~est" label, and a cost line ($ amount) renders beneath it when the model has a
  pricing match. For engines without real usage (cursor-cli, antigravity-cli), the
  Tokens line shows "~est" and the cost line is either an estimated cost or omitted
  cleanly (no $0.000000 misleading zero) when the model has no pricing row.
result: issue
reported: "Live sandbox run (Doki064/test-sandbox-repo PR #13, engine=claude-code-cli):
  sticky comment showed 'Tokens: review 3034' (no ~est) + 'Cost: $0.121149' — correct,
  real capture confirmed for claude-code-cli. Same PR with engine=copilot-cli: sticky
  comment showed 'Tokens: review ~est 1631' — still estimated, no cost line, DESPITE
  COPILOT_OTEL_FILE_EXPORTER_PATH being wired in prevue-review.yml (Plan 05). Debug
  probe added temporarily to the reusable workflow confirmed the OTEL directory is
  never created by the CLI at all, and `copilot --help` on the installed
  @github/copilot@1.0.61 has ZERO mention of OTEL/telemetry, and ~/.copilot never
  gets created. The env var this framework relies on does nothing on this CLI
  version — Copilot's real-token capture path (T-01 / WARNING 3) is provably
  non-functional in production despite Plan 03/05 claiming it fixed, and despite
  the dir-vs-file bug (T-01 thermos finding) being correctly fixed in usage.py."
severity: major
test: 1

### 2. Config precedence — env var overrides yml
expected: |
  With `.github/prevue.yml` setting `engine.model: some-model` AND workflow env
  `PREVUE_MODEL` (or `COPILOT_MODEL`) set to a different model, the review actually
  runs using the env-supplied model, not the yml value. Precedence order:
  workflow input/env > .github/prevue.yml > built-in defaults.
result: issue
reported: "Code inspection of .github/workflows/prevue-review.yml (the reusable
  workflow's 'Run review' step env: block, lines ~135-156): it sets
  GITHUB_TOKEN, PREVUE_STICKY_OWNER_LOGINS, PREVUE_ENGINE, PREVUE_CONSUMER_ROOT,
  PREVUE_CONFIG_PATH, the 3 per-engine secrets, COPILOT_OTEL_FILE_EXPORTER_PATH,
  and PREVUE_RESULT_FILE — there is no PREVUE_MODEL or COPILOT_MODEL passthrough,
  and workflow_call.inputs has no `model` input either. config.py's
  resolve_review_model(review_model_from_config, env_model) correctly implements
  'env wins over yml' as a pure function (unit-tested), and review.py reads
  os.environ.get('PREVUE_MODEL', os.environ.get('COPILOT_MODEL')) at the call
  site — but nothing in the actual public reusable-workflow interface lets a
  consumer set that env var for the review job. The declared CONFIG_PRECEDENCE
  ('workflow input > .github/prevue.yml > built-in defaults', WKFL-05/D-07) has
  no reachable 'workflow input' tier in production; only engine.model /
  engine.models.review in prevue.yml is actually usable by consumers today."
severity: major
test: 2

### 3. Per-role model tiering (classify vs review)
expected: |
  Setting `engine.models.classify` to a cheap/fast model and `engine.models.review`
  (or `engine.model`) to a different model in `.github/prevue.yml` causes the
  classification call and the review call to actually invoke different models —
  observable via engine_meta or logs showing distinct model names per call.
result: pass
notes: |
  Live test (Doki064/test-sandbox-repo PR #14): set engine.models.review to an
  invalid model string ("totally-fake-model-xyz-999") on main, engine.model left
  unset, engine=claude-code-cli. The Actions job failed with
  "Claude Code CLI exited 1: stdout='...\"total_cost_usd\":0,\"usage\":{...all
  zero...},\"terminal_reason\":\"completed\"...'" — reproduced the exact same
  zero-usage envelope shape locally by running
  `claude --model totally-fake-model-xyz-999 -p "hi" --output-format json`,
  confirming the bad string was passed through as the actual --model argument.
  Proves engine.models.review correctly threads into the real CLI invocation
  independent of engine.model (ENGN-09 wiring confirmed). Classify-side distinct
  model was not independently exercised (this PR's diff was unambiguous enough
  for deterministic path-based classification, so no llm_classify fallback call
  fired) — review-side per-role wiring is the part directly confirmed live.

### 4. raw_args passthrough (consumer escape hatch)
expected: |
  Setting `engine.raw_args: ["--some-flag", "value"]` in `.github/prevue.yml` (on
  base branch, not PR head) causes the review-engine CLI invocation to include
  those extra flags appended after all framework-generated argv. Providing raw_args
  as a plain string (not a list) is rejected with a clear config validation error.
result: pass
notes: |
  String-form rejection verified locally: EngineConfig(raw_args="--some-flag value")
  raises pydantic ValidationError with the exact D-10 message. List-form live test
  (Doki064/test-sandbox-repo PR #13, after correcting a PR base.sha staleness
  gotcha by merging main forward): set engine.raw_args: ["--this-flag-does-not-
  exist-xyz"] on main, engine=claude-code-cli. Actions job failed with
  "Claude Code CLI exited 1: stderr=\"error: unknown option
  '--this-flag-does-not-exist-xyz'\"" — proves raw_args is appended to the real
  argv sent to the CLI, exactly matching cli_adapter.py's documented order
  (base_argv → prompt-delivery flags → model flag → raw_args LAST).

### 5. Machine-readable output — job outputs + artifact
expected: |
  After a review run (success or failure), the job exposes GitHub Actions outputs
  (schema_version, conclusion, error_count, warning_count, info_count, tokens,
  cost_usd) usable by downstream `if:` steps, AND a `prevue-result.json` artifact
  is uploaded containing the full ReviewResult JSON with schema_version="1.0" —
  even when the review ends in a hard failure (auth error / non-functional engine),
  not just on success/skip/noop.
result: issue
reported: "Artifact half CONFIRMED WORKING: prevue-result.json uploaded correctly
  on a normal successful review (valid JSON, schema_version=1.0, findings[]) AND
  on the antigravity-cli hard-failure path (NonFunctionalEngineError — 328-byte
  artifact with schema_version/summary_markdown/degraded/engine_meta all present).
  Job-outputs half CONFIRMED BROKEN: added a temporary downstream job to the
  sandbox's caller workflow that reads needs.prevue.outputs.{schema_version,
  conclusion,error_count,warning_count,info_count,tokens,cost_usd} — every value
  came back empty in the live run, even though the 'Run review' step's own log
  showed 'Set output' fire for all 7 keys correctly. Root cause: .github/workflows
  /prevue-review.yml declares job-level `jobs.review.outputs: {...}` but has NO
  top-level `on.workflow_call.outputs:` block re-declaring those same keys —
  GitHub Actions requires that explicit workflow_call.outputs mapping for a
  caller's `needs.<job>.outputs.*` to ever be populated; job-level outputs alone
  do not propagate across a reusable-workflow boundary. OUTP-05's compact
  $GITHUB_OUTPUT contract is fully correct at the step level but unreachable by
  any consumer using this workflow as a `uses:` call, which is the delivery
  mechanism the whole project is built on."
severity: major
test: 5

### 6. Antigravity engine fails closed with clear error
expected: |
  Setting `engine: antigravity-cli` in the workflow config produces a clear,
  actionable error (NonFunctionalEngineError) explaining the engine is registered
  but not yet functional, and lists the still-functional engines
  (copilot-cli, claude-code-cli, cursor-cli) as alternatives — instead of
  attempting a broken headless-auth flow and failing silently or with a confusing
  low-level error.
result: pass
notes: |
  Live test (Doki064/test-sandbox-repo PR #13, engine=antigravity-cli): sticky
  comment posted exactly "Engine 'antigravity-cli' is registered but not yet
  functional; choose one of: copilot-cli, claude-code-cli, cursor-cli". The
  Antigravity CLI install step still ran and succeeded (agy 1.0.14 installed
  fine) but require_functional_adapter correctly blocked before any invocation
  attempt. prevue/review check run conclusion=failure (correctly blocks merge).
  prevue-result.json artifact still uploaded on this hard-fail path (see test 5).

### 7. Cursor-cli end-to-end review (no regression)
expected: |
  Running `engine: cursor-cli` on a real PR posts a sticky summary comment with
  findings, inline comments at correct file/line positions, a Tokens line
  (labeled ~est since Cursor's envelope has no usage fields), cost line omitted
  cleanly if no pricing match, and the prevue/review check run conclusion set
  correctly per min_severity_to_fail.
result: pass
notes: |
  Live test (Doki064/test-sandbox-repo PR #13, engine=cursor-cli): sticky comment
  posted with 10 valid findings at correct inline positions, "Tokens: review ~est
  2223" (no cost line — correct, default model has no pricing match), prevue/
  review check run conclusion=failure (correct per min_severity_to_fail: error,
  since error-severity findings were present). No regression from the prior
  cursor-cli JSON-envelope gap-closure (Plan 07).

### 8. GITHUB_OUTPUT write resilience
expected: |
  If writing the full result file fails for some reason, the workflow still
  continues to write the compact scalar values to $GITHUB_OUTPUT rather than
  aborting the whole output-emission step — downstream `if:` gates relying on
  job outputs keep working even when the artifact-file write path has a problem.
result: pass
notes: |
  Verified locally (not via sandbox — no live GH Actions surface exercises a
  broken result-file path without modifying the framework's own workflow).
  emit_machine_output(result_file=<a directory>) logs
  "prevue: failed to write result file ...: [Errno 21] Is a directory" to
  stderr, does NOT raise, and $GITHUB_OUTPUT still receives all 7 compact
  heredoc-form keys (schema_version, conclusion, error_count, ...). Matches
  commit c4589ec's intent exactly.

## Summary

total: 8
passed: 4
issues: 3
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Copilot CLI's real (non-estimated) token usage is captured via COPILOT_OTEL_FILE_EXPORTER_PATH in CI"
  status: failed
  reason: "Live sandbox run shows copilot-cli still reports ~est tokens; COPILOT_OTEL_FILE_EXPORTER_PATH has no effect on @github/copilot@1.0.61 — no OTEL mention in --help, ~/.copilot never created, exporter directory never appears"
  severity: major
  test: 1
  root_cause: "Either the env var name/mechanism is wrong for the currently-installed Copilot CLI version, or Copilot requires additional undocumented setup (config file, flag) to enable OTEL export at all. The 10-RESEARCH.md citation (ccusage.com/guide/copilot, MEDIUM-HIGH confidence) describing COPILOT_OTEL_FILE_EXPORTER_PATH may be stale or version-specific and was never live-verified against the pinned 1.0.61 CLI before being wired into prevue-review.yml."
  artifacts:
    - src/prevue/engines/usage.py (_parse_copilot_otel — correctly handles dir-vs-file, but is never fed real data)
    - .github/workflows/prevue-review.yml (COPILOT_OTEL_FILE_EXPORTER_PATH env wiring, Plan 05)
  missing:
    - "Live verification of what actually enables OTEL export in @github/copilot 1.0.x (check official GitHub Copilot CLI docs directly, not third-party citation)"
    - "If no CI-viable mechanism exists, flip copilot-cli's usage_capture to 'none' (honest estimate) matching the antigravity-cli precedent (D-03/functional-flag pattern), or find the correct enablement mechanism"

- truth: "Consumers can override the review model via a workflow input/env, taking precedence over .github/prevue.yml, per the declared CONFIG_PRECEDENCE"
  status: failed
  reason: "The reusable workflow's public interface (workflow_call inputs + Run review step env block) never forwards PREVUE_MODEL or COPILOT_MODEL from anywhere reachable by a consumer — the 'workflow input' precedence tier is architecturally unreachable in production even though the resolution function (resolve_review_model) is implemented and unit-tested correctly"
  severity: major
  test: 2
  root_cause: "T-02 (10-THERMOS) fixed the *internal* precedence bug (yml no longer beats env when both are present in-process), but no one added a `model` input to workflow_call.inputs or PREVUE_MODEL/COPILOT_MODEL to the Run review step's env: block — so in-process env resolution is correct but nothing ever populates that env var for a real consumer invocation."
  artifacts:
    - .github/workflows/prevue-review.yml (workflow_call.inputs block, lines ~4-29; Run review step env block, lines ~135-156)
    - src/prevue/config.py (resolve_review_model — correct logic, unreachable input)
  missing:
    - "Either a `model` input on workflow_call.inputs threaded into PREVUE_MODEL env for the Run review step, or explicit documentation that engine.model/engine.models.review in prevue.yml is the only supported override today (and CONFIG_PRECEDENCE's 'workflow input' tier should be removed or clarified)"

- truth: "Downstream jobs in a consumer's own workflow can chain automation on prevue's job outputs (schema_version, conclusion, error_count, warning_count, info_count, tokens, cost_usd) via needs.<job>.outputs.*"
  status: failed
  reason: "Live test with a downstream probe job reading needs.prevue.outputs.* got empty strings for all 7 keys, despite the Run review step's own GITHUB_OUTPUT writes succeeding (confirmed via 'Set output' log lines for every key)"
  severity: major
  test: 5
  root_cause: ".github/workflows/prevue-review.yml declares `jobs.review.outputs: {...}` but is missing the required top-level `on.workflow_call.outputs:` block that re-maps those same keys — this is a hard GitHub Actions requirement for reusable-workflow output propagation across the workflow_call boundary; job-level outputs alone never reach a caller's `needs.<job>.outputs`."
  artifacts:
    - .github/workflows/prevue-review.yml (missing on.workflow_call.outputs: block; jobs.review.outputs: exists but is orphaned)
  missing:
    - "Add: on.workflow_call.outputs: {schema_version: {value: ${{ jobs.review.outputs.schema_version }}}, conclusion: {...}, error_count: {...}, warning_count: {...}, info_count: {...}, tokens: {...}, cost_usd: {...}} to the reusable workflow's workflow_call block"
    - "A live re-verification (downstream job reading needs.<job>.outputs.*) after the fix, since this exact bug class is easy to reintroduce"
