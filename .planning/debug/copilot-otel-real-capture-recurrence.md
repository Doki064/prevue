---
status: diagnosed
trigger: "Investigate issue: copilot-otel-real-capture-recurrence -- Copilot CLI real-token OTEL capture still shows ~est (estimated) instead of real usage on a live PR, even after a gap-closure plan and two follow-up code-review fixes were applied and independently verified at the code level."
created: 2026-07-01T00:00:00Z
updated: 2026-07-01T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — Copilot CLI 1.0.67 only initializes/writes OTEL instrumentation when
  invoked with the -p/--prompt flag. prevue's copilot-cli spec uses base_argv=("copilot", "-s",
  "--no-ask-user") with prompt_delivery="stdin" (prompt piped via stdin, no -p flag at all).
  This means the real production invocation shape never triggers OTEL export, regardless of
  COPILOT_OTEL_FILE_EXPORTER_PATH being set correctly and the parser being fully correct.
test: Reproduced locally with a real npx @github/copilot@1.0.67 install, both invocation shapes,
  multiple repetitions, plus a flush-timing control and a debug-log control.
expecting: N/A - root cause confirmed, this is find_root_cause_only mode.
next_action: Return ROOT CAUSE FOUND to caller.

## Symptoms

expected: |
  With engine: copilot-cli on a live PR, using a real COPILOT_GITHUB_TOKEN secret in actual
  GitHub Actions CI, the sticky Tokens line shows real (non-estimated) token counts with no
  "~est" label -- confirming the chain: workflow env -> real Copilot CLI subprocess -> OTEL
  file write -> parser read -> estimated=False.
actual: |
  Live PR #31 (Doki064's test/sandbox repo, engine=copilot-cli): sticky comment still shows
  the ~est label instead of real token counts. This is a RECURRENCE -- same symptom as
  originally found on PR #13, supposedly fixed by:
    1. Gap-closure plan 10-09 (commits 2a75168, 60daa3e): rewrote _parse_copilot_otel in
       src/prevue/engines/usage.py for the real flat span-per-line JSONL schema, flipped
       usage_capture back to "otel-jsonl" in src/prevue/engines/spec.py.
    2. Code-review fix CR-01 (commit 4956f00): bumped CI-pinned Copilot CLI 1.0.61 -> 1.0.67
       in .github/scripts/install-engine-cli.sh.
    3. Code-review fix CR-02 (commit cdd96e8): fixed partial-field span parse corruption in
       _parse_copilot_otel to degrade to None instead of reporting estimated=False on bad data.
  10-VERIFICATION.md independently reproduced the CR-02 exploit and confirmed it now degrades
  to None. All previously-identified code-level bugs are confirmed fixed in isolation -- yet
  live end-to-end CI still does not produce real usage for copilot-cli.
errors: |
  None reported beyond the ~est label persisting. No CI log error message provided this time
  (unlike original PR #13 investigation which added a debug probe and found OTEL dir never
  created, and copilot --help on 1.0.61 had zero OTEL/telemetry mentions).
reproduction: |
  Test 1 in .planning/phases/10-boundary-contracts/10-UAT.md, live PR #31, engine=copilot-cli.
  No live GH Actions access -- static/code analysis only (workflow YAML, install script,
  usage.py, spec.py) plus verification of Copilot CLI 1.0.67's actual OTEL support.
started: |
  Original bug found on PR #13 pre-fix. Gap-closure plan 10-09 + code-review fixes CR-01/CR-02
  applied and code-level-verified this session. Fresh live re-verification on PR #31 today
  (2026-07-01) reproduced the same broken symptom.

## Eliminated

- hypothesis: The parser (_parse_copilot_otel) still has a schema bug not caught by prior fixes.
  evidence: Read usage.py fully (lines 190-314). Logic is correct and matches the real captured
    schema exactly (verified below). Ran the real function against a real Copilot-CLI-written
    OTEL file and it correctly summed tokens with estimated=False. Not the cause.
  timestamp: 2026-07-01T00:00:00Z

- hypothesis: COPILOT_OTEL_FILE_EXPORTER_PATH env var does not reach the copilot subprocess
    (dropped somewhere in the env-building chain).
  evidence: Traced full chain: workflow YAML env: block sets it on the "Run review" step ->
    process os.environ in the `prevue review` Python process -> flow.py:351 reads
    os.environ.get("COPILOT_OTEL_FILE_EXPORTER_PATH") -> cli_adapter.py:76 builds subprocess env
    as `{**os.environ, spec.secret_env: token}` (a full copy of the parent's environ, so the var
    is preserved) -> subprocess_invoke.py passes env through unaltered to subprocess.run. No
    stripping/filtering anywhere in this chain. Not the cause.
  timestamp: 2026-07-01T00:00:00Z

- hypothesis: Copilot CLI still pinned to a version (e.g. stale 1.0.61) without OTEL support,
    or CR-01's version bump didn't actually land.
  evidence: install-engine-cli.sh:8 confirmed `npm install -g @github/copilot@1.0.67`. Installed
    and ran that exact version locally via npx; `copilot help monitoring` documents OTEL support
    fully, confirming 1.0.67 genuinely supports COPILOT_OTEL_FILE_EXPORTER_PATH. Not the cause.
  timestamp: 2026-07-01T00:00:00Z

- hypothesis: COPILOT_OTEL_FILE_EXPORTER_PATH must point at a pre-existing directory / the
    workflow never mkdir's the runner.temp/copilot-otel path, so the exporter silently no-ops.
  evidence: Tested locally: pointed COPILOT_OTEL_FILE_EXPORTER_PATH at a path whose parent
    directory did not exist. Copilot CLI created the parent directory itself and wrote the file
    successfully when invoked with -p. Not the cause (though see Evidence: the workflow's path
    is used as a FILE by the CLI, and usage.py handles both file and dir cases correctly via
    path.is_dir(), so this isn't a problem either way).
  timestamp: 2026-07-01T00:00:00Z

## Evidence

- timestamp: 2026-07-01T00:00:00Z
  checked: src/prevue/engines/spec.py CLI_ENGINE_SPECS copilot-cli entry
  found: |
    base_argv=("copilot", "-s", "--no-ask-user"), prompt_delivery="stdin", model_flag="env".
    No -p/--prompt flag anywhere in base_argv; the prompt is delivered via stdin per
    cli_adapter.py's prompt_delivery="stdin" branch.
  implication: The actual production copilot invocation never passes -p/--prompt.

- timestamp: 2026-07-01T00:00:00Z
  checked: `npx -y @github/copilot@1.0.67 --help` output
  found: |
    -s, --silent  Output only the agent response (no stats), useful for scripting with -p
    -p, --prompt <text>  Execute a prompt in non-interactive mode (exits after completion)
    Usage banner: "Start an interactive session to chat with Copilot, or use -p/--prompt for
    non-interactive scripting."
  implication: -s is explicitly documented as a companion flag to -p ("useful for scripting
    with -p"), and -p is what triggers "non-interactive mode". Without -p, behavior/mode is
    ambiguous from docs alone — needed to test directly.

- timestamp: 2026-07-01T00:00:00Z
  checked: Real local install of the exact CI-pinned Copilot CLI 1.0.67 (via `npx -y
    @github/copilot@1.0.67`), multiple controlled invocations comparing "-p" vs
    stdin-only delivery, with COPILOT_OTEL_FILE_EXPORTER_PATH pointed at a fresh path each time.
  found: |
    - `copilot -s --no-ask-user -p "<prompt>"` (has -p): OTEL file IS created at the configured
      path every time (tested 1x standalone + repeated in later tests, always present).
    - `echo "<prompt>" | copilot -s --no-ask-user` (stdin only, matches prevue's EXACT argv
      shape and prompt_delivery, no -p flag): OTEL file is NEVER created. Tested 4 separate
      times (otel-B1, otel-B2, otel-C, otel-E) with different prompts, all runs exit 0 and
      correctly answer the piped-in prompt (proving stdin-delivery itself works fine for
      getting a response) — but zero OTEL output every single time.
    - Ruled out async flush delay: slept 3s after process exit in one run; file still never
      appeared.
    - Ruled out silent/quiet OTel failure: ran with `--log-level debug` and
      `OTEL_LOG_LEVEL=DEBUG`; grepped output for otel/telemetry/export — zero matching lines
      at any level, meaning the OTel subsystem does not even attempt initialization on this
      code path, it isn't failing after starting.
  implication: |
    THIS IS THE ROOT CAUSE. Copilot CLI 1.0.67 only initializes and writes OTEL
    instrumentation when invoked in explicit "-p" non-interactive mode. prevue's
    copilot-cli CliEngineSpec uses prompt_delivery="stdin" with base_argv containing no -p
    flag — this is a DIFFERENT invocation mode than the one every prior fix (10-09, CR-01,
    CR-02, and 10-VERIFICATION.md's exploit repro) was diagnosed and tested against. All
    of 10-VERIFICATION.md's local checks either read a pre-existing fixture file
    (tests/fixtures/usage/copilot_otel.jsonl) or exercised _parse_copilot_otel as a pure
    function — none of them ran the real copilot subprocess via prevue's actual
    stdin-delivery invocation path end-to-end. The original spec.py comment (line 115-116)
    itself says the local install confirming OTEL works was tested via `copilot help
    monitoring` (a docs check) — not via the actual stdin-piped invocation shape prevue uses
    in production. This gap in the verification's test surface is why the fix held "in
    isolation" (parser correctness, CLI version, CR-02 corruption safety) but never held
    end-to-end: the subprocess invocation shape itself silently never produces OTEL data to
    parse in the first place.

- timestamp: 2026-07-01T00:00:00Z
  checked: 10-VERIFICATION.md and spec.py's supersession comment (lines 112-127)
  found: |
    spec.py's comment says "A local install of the real Copilot CLI (`gh copilot`, v1.0.67)
    confirms OTEL file export IS real and documented (`copilot help monitoring`)" — this is a
    DOCS check, not an actual invocation test matching prevue's real argv/stdin shape.
    10-VERIFICATION.md's "Human Verification Required" section explicitly flags that a live
    CI run with the real subprocess was the one thing that could not be verified locally, and
    correctly kept status as human_needed rather than passed — the verification process
    behaved correctly given its constraints; the blind spot was that no one (including this
    investigation's predecessor sessions) tried invoking the real CLI via stdin (prevue's
    actual delivery mode) instead of -p, when locally validating "Copilot CLI's OTEL support."
  implication: Confirms this is a genuinely new finding not previously tested, not a re-check
    of something already ruled out.

## Resolution

root_cause: |
  Copilot CLI 1.0.67 only initializes/emits OpenTelemetry instrumentation (spans + metrics,
  including the file-exporter JSONL that COPILOT_OTEL_FILE_EXPORTER_PATH configures) when
  invoked in explicit "-p"/"--prompt" non-interactive mode. prevue's copilot-cli
  CliEngineSpec (src/prevue/engines/spec.py) is declared with
  base_argv=("copilot", "-s", "--no-ask-user") and prompt_delivery="stdin" — i.e. the prompt
  is piped to the CLI's stdin rather than passed via -p/--prompt. This stdin-delivery
  invocation shape produces a correct chat response (proving stdin delivery itself is
  functionally fine) but never triggers OTEL initialization at all — confirmed via a real,
  repeated, deterministic local reproduction against the exact CI-pinned CLI version
  (1.0.67), including ruling out async-flush timing and confirming zero OTel-related debug
  log output on this code path. Every prior fix (10-09's parser rewrite, CR-01's version
  bump, CR-02's corruption-safety fix) is correct in isolation and was verified against
  either a static fixture file or a `-p`-based local invocation / `copilot help monitoring`
  docs check — none of them exercised prevue's actual stdin-based subprocess invocation
  shape, so the gap was never caught until this live-CI recurrence. The parser, the env
  wiring, and the CLI version pin are all correct; the underlying subprocess invocation
  mode itself is the one thing that has never actually produced real OTEL data end-to-end
  for prevue's copilot-cli adapter.
fix: ""
verification: |
  Independently re-verified by the orchestrator (not just this debug agent's word) after the
  user reported a local test showing OTEL working for "both -p and non -p" — a direct
  contradiction on its face. Reran the experiment fresh, twice:
    1. Fresh, isolated HOME (no pre-existing ~/.copilot session — mimics a CI runner's clean
       environment) + COPILOT_GITHUB_TOKEN set directly via env var (not gh auth reuse) +
       prevue's EXACT argv (`copilot -s --no-ask-user`) + prompt piped via stdin: CLI answered
       correctly ("pong"), but NO OTEL file was created.
    2. Same fresh HOME + same token, but with `-p "<prompt>"` instead of piped stdin: OTEL
       file WAS created (real spans, ~15KB).
    3. Re-ran piped-stdin again against the user's actual warm/existing ~/.copilot session
       (ruling out fresh-vs-warm-session as a confound): still NO OTEL file.
  Asked the user directly how their "non -p" test that produced OTEL was actually invoked.
  Answer: typed the prompt at an interactive `copilot` chat prompt (real TTY), not piped or
  redirected. This is a THIRD delivery mode — distinct from both prevue's piped/redirected
  stdin (a closed pipe, EOF-terminated, no TTY) and from `-p`. Real interactive TTY sessions
  reliably trigger OTEL (the CLI's default day-to-day usage path); prevue's actual
  piped-stdin subprocess invocation does not, confirmed 3 total independent times now
  (1 by the original debug agent, 2 more directly by the orchestrator). Root cause and
  suggested fix direction (switch to -p/argv-based delivery) stand confirmed, not weakened,
  by this cross-check.
files_changed: []

## THIRD Recurrence (2026-07-06)

trigger: "Live re-verification of Test 1 (10-UAT.md) via a fresh PR (Doki064/test-sandbox-repo
  #15) after plan 10-10's -p/argv delivery fix landed. Also had to first fix an unrelated
  live-test blocker: the sandbox repo's own caller workflow (.github/workflows/prevue-review.yml)
  was missing the copilot-github-token secret passthrough (dropped in sandbox commit 5128630,
  2026-06-30) — fixed and pushed directly to sandbox main (commit 7d82f89) with explicit user
  authorization, before the PR could even authenticate."
actual: |
  With the secret fixed, PR #15's review ran successfully end-to-end (real copilot-cli
  completion, 3 valid findings posted, 17s duration) — confirming the 10-10 -p/argv fix IS
  reached live (tiny diff, well under the 64 KiB ceiling). But the sticky comment's Tokens line
  still showed "~est 1571", not real counts. Downloaded the prevue-result.json artifact and
  confirmed engine_meta.tokens.estimated=true.
new_root_cause: |
  Different bug from rounds 1-2. Directly reproduced against the real, CI-pinned Copilot CLI
  1.0.67 binary (npm install -g @github/copilot@1.0.67, isolated HOME, own valid GitHub token
  via `gh auth token`):
    - Test A: COPILOT_OTEL_FILE_EXPORTER_PATH pointed at a path that already exists as an
      EMPTY DIRECTORY (mkdir'd before invocation — exactly what tempfile.mkdtemp() produces),
      invoked with -p. Result: directory stays empty after a correct completion. No OTEL data
      written anywhere.
    - Test B (control): COPILOT_OTEL_FILE_EXPORTER_PATH pointed at a path that does NOT yet
      exist, invoked with -p. Result: Copilot CLI creates a REGULAR FILE (not a directory) at
      that exact path, containing real NDJSON OTEL spans (~15KB).
  Conclusion: Copilot's OTEL file exporter writes a single file AT the exact configured path,
  creating it only if the path doesn't already exist. It never treats the path as a directory
  to write *.jsonl files into. src/prevue/engines/cli_adapter.py:227-238 (the WR-01 code-review
  fix for multi-call OTEL cross-contamination) calls
  `otel_path = tempfile.mkdtemp(dir=base_otel_dir)`, which pre-creates the exact leaf path as an
  empty directory before Copilot ever runs — silently defeating OTEL writing. usage.py's
  `_parse_copilot_otel` directory-glob handling (path.is_dir() branch) was built on the same
  wrong assumption and is not itself buggy — no parser change needed.
suggested_fix: |
  In cli_adapter.py's review() method, replace `tempfile.mkdtemp(dir=base_otel_dir)` (which
  creates a directory on disk) with a per-call path construction that does NOT touch the
  filesystem, e.g. `otel_path = os.path.join(base_otel_dir, f"{uuid.uuid4().hex}.jsonl")` —
  still unique per call (preserving WR-01's original goal of no cross-call contamination), but
  Copilot's exporter finds a non-existent path and creates the file itself, exactly like Test B.
verification_status: "Root cause confirmed via direct reproduction, not yet fixed in code.
  Recorded in 10-UAT.md gap 1 (fix_update_2026-07-06_THIRD_RECURRENCE) for gap-closure planning."

## Fix Applied (2026-07-06)

files_changed:
  - src/prevue/engines/cli_adapter.py
  - tests/test_copilot_adapter.py
diff_shape: |
  review()'s otel_path construction changed from:
    otel_path = tempfile.mkdtemp(dir=base_otel_dir)
  to:
    otel_path = os.path.join(base_otel_dir, f"{uuid.uuid4().hex}.jsonl")
  `os.makedirs(base_otel_dir, exist_ok=True)` and the surrounding
  `try/except OSError: otel_path = None` degrade block are unchanged in
  structure. Per-call path uniqueness (WR-01's original goal) is preserved —
  only the leaf path is no longer pre-created on disk as a directory (or
  anything else).

  Test changes: TestOtelPerCallIsolation.test_two_calls_get_distinct_otel_subdirs
  renamed to test_two_calls_get_distinct_otel_paths; `assert os.path.isdir(p)`
  replaced with `assert not os.path.exists(p)` (regression guard) plus a new
  `assert p.endswith(".jsonl")`. test_mkdtemp_oserror_degrades_to_job_wide_dir_
  instead_of_crashing renamed to test_makedirs_oserror_degrades_to_job_wide_dir_
  instead_of_crashing, patching os.makedirs instead of the now-unused
  tempfile.mkdtemp (tempfile.mkdtemp is no longer called by production code).
verification: "uv run pytest tests/test_copilot_adapter.py -x -q: 41 passed.
  Full uv run pytest -x -q: 835 passed, zero regressions."
status: "Code-level fix applied and verified. Live re-verification on a real PR
  (real COPILOT_GITHUB_TOKEN, real Copilot CLI 1.0.67 subprocess) is STILL
  REQUIRED before this gap can be marked resolved — code-level fixes for this
  exact gap (real OTEL token capture) have now failed live verification twice
  before (rounds 2 and 3), so this debug log does not claim resolution from
  code-level evidence alone. 10-UAT.md gap 1 status remains 'failed' pending
  that live confirmation."
