---
status: complete
phase: 10-boundary-contracts
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md, 10-04-SUMMARY.md, 10-05-SUMMARY.md, 10-06-SUMMARY.md, 10-07-SUMMARY.md, 10-08-SUMMARY.md, 10-09-SUMMARY.md, 10-10-SUMMARY.md, 10-11-SUMMARY.md, 10-VERIFICATION.md]
started: 2026-07-01T09:51:21Z
updated: 2026-07-06T11:30:00Z
---

## Current Test

[testing complete — all gaps resolved and live-confirmed]

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
result: pass
notes: |
  FOURTH live re-test (2026-07-06), PR #16 (Doki064/test-sandbox-repo),
  engine=copilot-cli, after pushing gap-closure plan 10-11's fix
  (gsd/phase-10-boundary-contracts, commit ae6523c) to the framework branch the
  sandbox's caller workflow points at. Sticky comment shows "Tokens: review 39566"
  — real count, no "~est" label. Cost line correctly omitted (default model has no
  pricing match). This confirms the THIRD-recurrence root cause (tempfile.mkdtemp
  pre-creating the OTEL leaf path as an empty directory) is fixed by the
  uuid-based non-touching path construction. Gap closed after 3 recurrences.

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
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Copilot CLI's real (non-estimated) token usage is captured via COPILOT_OTEL_FILE_EXPORTER_PATH in CI"
  status: resolved
  reason: "Post-fix re-verification (live PR #31, engine=copilot-cli): sticky comment
    still shows ~est instead of real token counts. This is a RECURRENCE after
    gap-closure plan 10-09 (rewrote _parse_copilot_otel for the real flat span-per-line
    JSONL schema, flipped usage_capture back to otel-jsonl) and code-review fixes
    CR-01 (commit 4956f00, CLI pin bumped 1.0.61 -> 1.0.67) and CR-02 (commit cdd96e8,
    partial-field span parse corruption fix). Those fixes were verified at the code
    level (10-VERIFICATION.md reproduced the CR-02 exploit and confirmed it now
    degrades to None) but the live end-to-end path is still not producing real usage.
    Needs fresh diagnosis: prior root-cause assumed CLI 1.0.67 actually emits OTEL
    spans when COPILOT_OTEL_FILE_EXPORTER_PATH is set — that assumption itself may
    be wrong, or the env var may not be reaching the CLI process, or the OTEL file
    may not be getting written/read where expected in the live CI job."
  severity: major
  test: 1
  root_cause: "Copilot CLI 1.0.67 only initializes OpenTelemetry (spans/metrics, including
    the COPILOT_OTEL_FILE_EXPORTER_PATH file exporter) when invoked with an explicit
    -p/--prompt flag (non-interactive prompt-as-argv mode). Prevue's copilot-cli
    CliEngineSpec (src/prevue/engines/spec.py) uses base_argv=(\"copilot\", \"-s\",
    \"--no-ask-user\") with prompt_delivery=\"stdin\" — the prompt is piped via stdin
    and -p is never passed. Confirmed via 4 repeated local runs of the CI-pinned
    1.0.67 CLI: `copilot -s --no-ask-user -p \"<prompt>\"` creates the OTEL file every
    time; `echo \"<prompt>\" | copilot -s --no-ask-user` (prevue's exact invocation
    shape) never creates it, even with --log-level debug + OTEL_LOG_LEVEL=DEBUG (zero
    otel/telemetry log lines — the subsystem never attempts init on the stdin path).
    The parser, env-var wiring, and CLI version pin are all independently correct
    (parser verified against a real -p-produced OTEL file); every prior fix was
    verified against a static fixture or a -p-based local check, never against
    prevue's actual stdin-delivery subprocess invocation — which is why it held in
    isolation (10-VERIFICATION.md) but never held end-to-end."
  artifacts:
    - src/prevue/engines/spec.py (copilot-cli CliEngineSpec: base_argv + prompt_delivery="stdin" — never passes -p, so OTEL never initializes)
    - src/prevue/engines/cli_adapter.py (_invoke stdin-delivery branch — builds the argv/stdin actually executed; reflects the shape that avoids -p)
    - src/prevue/engines/usage.py (_parse_copilot_otel — confirmed correct, not implicated)
    - .github/workflows/prevue-review.yml, .github/workflows/prevue-command-run.yml (COPILOT_OTEL_FILE_EXPORTER_PATH env wiring — confirmed correct, not implicated)
    - .github/scripts/install-engine-cli.sh (Copilot CLI 1.0.67 pin — confirmed correct, not implicated)
    - "THIRD RECURRENCE (2026-07-06): src/prevue/engines/cli_adapter.py:227-238 (review() method, WR-01's per-call OTEL isolation fix) — `otel_path = tempfile.mkdtemp(dir=base_otel_dir)` pre-creates the exact leaf path as an empty directory before invocation; Copilot's file exporter needs a non-existent path to create as a FILE, and silently no-ops when a directory already occupies that exact path. Confirmed via direct local reproduction against the real CI-pinned 1.0.67 binary (see fix_update_2026-07-06_THIRD_RECURRENCE)."
  missing:
    - "Change copilot-cli's invocation to use -p/--prompt (e.g. prompt_delivery=\"argv\" or an argv-based delivery mode) instead of stdin, so the CLI actually enters its OTEL-emitting non-interactive code path"
    - "Re-verify prompt-size handling once -p is used: -p takes the prompt as a single argv string rather than piping arbitrary-length stdin — confirm existing max_prompt_bytes guard covers this or that -p has no practical length limit for this codebase's prompt sizes"
    - "THIRD RECURRENCE fix: in cli_adapter.py's review() method, replace `tempfile.mkdtemp(dir=base_otel_dir)` (creates an empty directory) with a per-call path construction that does NOT pre-create anything on disk — e.g. `os.path.join(base_otel_dir, f\"{uuid.uuid4().hex}.jsonl\")` — so Copilot's file exporter finds a non-existent path and creates the file itself. Preserves WR-01's original goal (per-call isolation, no cross-call OTEL contamination under max_review_calls > 1) without breaking OTEL emission. usage.py's _parse_copilot_otel already handles both file and directory paths via path.is_dir(), so no parser change is needed — only the path passed in needs to stop being a pre-created directory."
  debug_session: ".planning/debug/copilot-otel-real-capture-recurrence.md"
  fix_update_2026-07-05: "Gap-closure plan 10-10 (commits 7b41854/7a93035/846b071/cd3285e)
    implemented the missing items above: CliEngineSpec.argv_prompt_max_bytes + a new
    size-gated \"stdin-or-argv\" prompt_delivery mode (64 KiB ceiling) — copilot-cli now
    uses -p argv delivery for prompts at/under the ceiling (reaching the OTEL-emitting
    code path) and keeps the proven stdin fallback above it (no 01-07 ARG_MAX regression).
    10-VERIFICATION.md re-confirmed this at the code level (21/21 must-haves, 828 tests
    passing) and a targeted code review (10-REVIEW.md, 0 critical/2 warning) found the new
    branch correct in isolation. status remains 'failed' (not resolved) — given this exact
    item has now recurred twice after being marked resolved from code-level evidence alone,
    it is deliberately held open until one more live GitHub Actions run (real
    COPILOT_GITHUB_TOKEN, PR under ~50 KB of diff/prompt content) confirms the sticky
    comment shows real (non-~est) token counts end-to-end in production."
  fix_update_2026-07-06_THIRD_RECURRENCE: "Live re-test performed this session (PR #15,
    Doki064/test-sandbox-repo, tiny diff well under the 64 KiB ceiling): the 10-10 -p/argv
    fix IS reached live (confirmed: real completion, 17s duration, findings posted) but the
    Tokens line still showed '~est 1571', not real counts. Root cause is NEW and DIFFERENT
    from rounds 1-2, found via direct local reproduction against the real, CI-pinned
    Copilot CLI 1.0.67 binary (npm install -g @github/copilot@1.0.67, isolated HOME, own
    valid GitHub token):
      - Test A: set COPILOT_OTEL_FILE_EXPORTER_PATH to a path that already exists as an
        EMPTY DIRECTORY (created via mkdir before invoking, i.e. exactly what
        tempfile.mkdtemp() produces) + invoke with -p. Result: directory stays EMPTY after
        the CLI exits 0 with a correct completion. No jsonl file written anywhere.
      - Test B (control): set COPILOT_OTEL_FILE_EXPORTER_PATH to a path that does NOT yet
        exist + invoke with -p. Result: Copilot CLI creates a REGULAR FILE (not a
        directory) at that exact path, containing real NDJSON OTEL spans (~15KB, `file`
        confirms 'New Line Delimited JSON text data').
      Conclusion: Copilot's OTEL file exporter writes a single file AT the exact path
      given, creating it only if the path does not already exist — it never treats the
      configured path as a directory to write *.jsonl files inside. WR-01's code-review
      fix (src/prevue/engines/cli_adapter.py:227-238, commit unknown — introduced to stop
      multi-call OTEL cross-contamination) calls
      `otel_path = tempfile.mkdtemp(dir=base_otel_dir)`, which PRE-CREATES the exact leaf
      path as an empty directory before copilot ever runs. This silently defeats OTEL
      writing entirely: the CLI can't write a file where a directory already exists at
      that exact path, and fails silently (no crash, no error surfaced — completion still
      succeeds normally). usage.py's `_parse_copilot_otel` directory-glob handling
      (path.is_dir() branch) was built on the same wrong assumption (that Copilot writes
      into a directory), which is why it never caught this: it's not a parser bug, it's an
      invocation-shape bug identical in spirit to rounds 1-2 but in the opposite direction
      (over-eager pre-creation instead of missing -p)."
  fix_update_2026-07-06_FOURTH_ROUND: "Gap-closure plan 10-11 applied the fix per
    fix_update_2026-07-06_THIRD_RECURRENCE's `missing` item: cli_adapter.py's review()
    now builds otel_path via `os.path.join(base_otel_dir, f\"{uuid.uuid4().hex}.jsonl\")`
    instead of `tempfile.mkdtemp(dir=base_otel_dir)` — the leaf path is never pre-created
    on disk, only base_otel_dir itself. Per-call path uniqueness (WR-01) is preserved.
    TestOtelPerCallIsolation updated: test_two_calls_get_distinct_otel_paths now asserts
    `not os.path.exists(p)` (regression guard against a fourth recurrence) plus
    `p.endswith('.jsonl')`; the OSError-degrade test now patches os.makedirs (the only
    remaining filesystem call) instead of the now-unused tempfile.mkdtemp. Full test
    suite green (835 passed), zero regressions."
  fix_update_2026-07-06_LIVE_CONFIRMATION: "Pushed gsd/phase-10-boundary-contracts
    (commit ae6523c, includes plan 10-11's fix) to origin, then live re-tested via a
    fresh PR #16 (Doki064/test-sandbox-repo, engine=copilot-cli). Sticky comment showed
    'Tokens: review 39566' — real count, no '~est' label, cost line correctly omitted
    (no pricing match for default model). Confirms the fix holds end-to-end in
    production, not just at the code level. status flipped to 'resolved' — this is the
    first of the 3 recurrences of this gap to be confirmed by a live GitHub Actions run
    rather than code-level evidence alone."

- truth: "Consumers can override the review model via a workflow input/env, taking precedence over .github/prevue.yml, per the declared CONFIG_PRECEDENCE"
  status: resolved
  reason: "Gap-closure plan 10-08 added PREVUE_MODEL: ${{ inputs.model }} to the Run review step's env block in prevue-review.yml, making the 'workflow input' precedence tier reachable. Confirmed present in codebase during this session's re-verification."
  severity: major
  test: 2

- truth: "Downstream jobs in a consumer's own workflow can chain automation on prevue's job outputs (schema_version, conclusion, error_count, warning_count, info_count, tokens, cost_usd) via needs.<job>.outputs.*"
  status: resolved
  reason: "Gap-closure plan 10-08 added the required top-level on.workflow_call.outputs: block to prevue-review.yml, re-mapping jobs.review.outputs.* so they propagate across the workflow_call boundary. Confirmed present in codebase during this session's re-verification."
  severity: major
  test: 5
