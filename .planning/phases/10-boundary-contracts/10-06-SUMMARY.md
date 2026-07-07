---
phase: 10-boundary-contracts
plan: "06"
subsystem: engines
tags: [engn-10, perf-03, antigravity, pricing, d-06b, d-12, t-10-17, t-10-18, t-10-19, t-10-21, checkpoint]
dependency_graph:
  requires: [10-02, 10-03, 10-05]
  provides:
    - "antigravity-cli install case in install-engine-cli.sh with checksum gate (T-10-17)"
    - "ANTIGRAVITY_API_KEY conditional secret in prevue-review.yml (T-10-20)"
    - "pseudo-TTY script -qec wrapper in cli_adapter.py for antigravity (T-10-21)"
    - ".github/workflows/update-pricing.yml scheduled pricing-bump PR workflow (D-06b)"
    - "SECURITY.md Antigravity install trust + pricing snapshot trust documentation"
  affects:
    - ".github/scripts/install-engine-cli.sh (antigravity-cli case added)"
    - ".github/workflows/prevue-review.yml (antigravity secret added)"
    - ".github/workflows/review.yml (antigravity secret pass-through added)"
    - "src/prevue/engines/cli_adapter.py (pseudo-TTY wrapper for antigravity argv delivery)"
    - "tests/test_reusable_workflow_yaml.py (6 new antigravity assertions)"
    - "tests/test_engine_contract.py (vendor_argv assertion updated for bash -c wrapper)"
tech_stack:
  added: []
  patterns:
    - "curl-download-then-exec with optional sha256sum gate (mirrors Cursor pattern)"
    - "conditional secret injection gated on inputs.engine == 'antigravity-cli'"
    - "pseudo-TTY via script -qec with prompt in env var _AGY_PROMPT (injection-safe)"
    - "ANSI strip + CR removal via sed -r + tr -d piped through bash -c"
    - "scheduled cron workflow with diff-then-branch-then-PR pattern (no merge step)"
key_files:
  created:
    - .github/workflows/update-pricing.yml
  modified:
    - .github/scripts/install-engine-cli.sh
    - .github/workflows/prevue-review.yml
    - .github/workflows/review.yml
    - src/prevue/engines/cli_adapter.py
    - tests/test_reusable_workflow_yaml.py
    - tests/test_engine_contract.py
    - SECURITY.md
decisions:
  - "Pseudo-TTY wrapper implemented in cli_adapter.py argv branch keyed on spec.name == antigravity-cli — prompt stored in _AGY_PROMPT env var to avoid shell-quoting injection risk"
  - "Prompt injection safety: inner agy invocation uses $var expansion inside script -qec, not direct shell-interpolation of prompt content"
  - "update-pricing.yml uses gh pr create (pre-installed on ubuntu-latest) rather than peter-evans/create-pull-request to avoid new action SHA pinning"
  - "Comments in update-pricing.yml avoid the exact strings 'auto-merge' and '--auto' so the grep acceptance gate (! grep -qiE) passes"
  - "test_vendor_argv[antigravity-cli] updated to assert bash -c wrapper form instead of raw agy argv — matches new pseudo-TTY implementation"
  - "review.yml dogfood workflow updated to pass antigravity-api-key through to the reusable workflow (required by test_review_yml_named_secrets_no_inherit)"
metrics:
  duration: 10min
  completed: "2026-06-29"
  tasks: 2
  files: 7
---

# Phase 10 Plan 06: Antigravity Install + Pricing Bump Workflow Summary

Antigravity CLI installs in-workflow with an optional checksum gate (mirroring Cursor), gets its secret conditionally in the Run-review env, runs through a pseudo-TTY `script -qec` wrapper to survive the non-TTY stdout-drop bug in CI, and a scheduled `update-pricing.yml` workflow bumps the vendored LiteLLM snapshot via a human-reviewed PR (never merged automatically). SECURITY.md documents both new trust surfaces.

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-29T11:16:57Z
- **Completed:** 2026-06-29T11:26:57Z
- **Tasks:** 2 (+ 1 checkpoint awaiting human verification)
- **Files modified:** 7

## Accomplishments

### Task 1: Antigravity install + secret pass-through + pseudo-TTY invocation

- Added `antigravity-cli)` case to `.github/scripts/install-engine-cli.sh`:
  - Downloads `https://antigravity.google/cli/install.sh` to `$RUNNER_TEMP/antigravity-install.sh`
  - Optional `PREVUE_ANTIGRAVITY_INSTALL_SHA256` checksum gate via `sha256sum -c -` (mirrors Cursor pattern, T-10-17)
  - Executes with `bash`, then verifies `command -v agy`
  - Uses download-then-exec pattern (not curl-pipe-to-bash)
- Added `antigravity-api-key: required: false` to `prevue-review.yml` `workflow_call` secrets block
- Added `ANTIGRAVITY_API_KEY: ${{ inputs.engine == 'antigravity-cli' && secrets.antigravity-api-key || '' }}` to Run-review step env (T-10-20: not leaked to non-Antigravity runs)
- Added `antigravity-api-key` to dogfood `review.yml` secrets pass-through
- Implemented Pitfall 2 pseudo-TTY wrapper in `cli_adapter.py` for `antigravity-cli`:
  - Detected by `spec.name == "antigravity-cli"` in the `prompt_delivery == "argv"` branch
  - Prompt stored in `_AGY_PROMPT` env var (injection-safe: no shell-quoting of prompt content)
  - Inner cmd assembled with `shlex.quote` and passed to `script -qec '<inner_cmd>' /dev/null | sed -r 's/\x1B\...//g' | tr -d '\r'`
  - Wrapped invocation runs via `["bash", "-c", wrapper_cmd]`
- Extended `tests/test_reusable_workflow_yaml.py` with 6 new tests: install case existence, checksum gate, download-then-exec pattern, workflow_call secret, engine-gated env, pseudo-TTY wrapper presence
- Updated `tests/test_engine_contract.py` `test_vendor_argv[antigravity-cli]`: now asserts `cmd[:2] == ["bash", "-c"]` and `"script -qec" in cmd[2]` (the pre-wrapper assertion was `cmd[:2] == ["agy", "-p"]`)

### Task 2: Scheduled pricing-bump workflow + SECURITY.md note (D-06b)

- Created `.github/workflows/update-pricing.yml`:
  - Trigger: `on: schedule: cron: "0 6 * * 1"` (Mondays 06:00 UTC) + `workflow_dispatch`
  - Permissions: `contents: write` + `pull-requests: write` only (T-10-19, no `write-all`)
  - SHA-pinned `actions/checkout@df4cb1c...` (matches repo convention)
  - Steps: fetch latest LiteLLM JSON → diff → commit to branch → `gh pr create` with review checklist
  - No merge step, no approve step, no `auto-merge` or `--auto` flag (T-10-18 hard requirement)
  - `zizmor` audit: 0 new findings (31 suppressed, all pre-existing)
  - `actionlint`: exits 0
- Added two new sections to `SECURITY.md`:
  - **Antigravity CLI install-script trust (T-10-17 / D-12):** documents curl-download-then-exec, optional `PREVUE_ANTIGRAVITY_INSTALL_SHA256` checksum gate, recommendation to pin for merge-gate workflows
  - **LiteLLM pricing snapshot trust (SKIL-04 / D-06a / D-06b):** documents never-fetched-at-review-time posture, scheduled human-reviewed PR bump, no automatic merge
  - Existing D-08 content preserved: `test_security_md_documents_d08_live_verification` GREEN

## Task Commits

1. **Task 1: Antigravity install + secret pass-through + pseudo-TTY wrapper** - `1351dc6` (feat)
2. **Task 2: Scheduled pricing-bump workflow + SECURITY.md trust notes** - `c47af4e` (feat)

## Files Created/Modified

- `.github/scripts/install-engine-cli.sh` — `antigravity-cli)` case with checksum gate
- `.github/workflows/prevue-review.yml` — `antigravity-api-key` secret + `ANTIGRAVITY_API_KEY` env (engine-gated)
- `.github/workflows/review.yml` — `antigravity-api-key` pass-through added
- `.github/workflows/update-pricing.yml` — NEW: scheduled pricing-bump PR workflow (D-06b)
- `src/prevue/engines/cli_adapter.py` — pseudo-TTY wrapper for antigravity-cli argv branch
- `tests/test_reusable_workflow_yaml.py` — 6 new antigravity assertions
- `tests/test_engine_contract.py` — vendor_argv assertion updated for bash -c wrapper form
- `SECURITY.md` — two new trust surface sections (Antigravity install + pricing snapshot)

## Verification Results

- `bash -n .github/scripts/install-engine-cli.sh` — exit 0
- `actionlint .github/workflows/prevue-review.yml .github/workflows/update-pricing.yml` — exit 0
- `uv run pytest tests/test_reusable_workflow_yaml.py -x -q` — 25 passed
- `uv run pytest tests/test_engine_contract.py -x -q` — green (including D-08 test)
- `grep -q 'antigravity-cli' .github/scripts/install-engine-cli.sh` — PASS
- `grep -q 'PREVUE_ANTIGRAVITY_INSTALL_SHA256' ...install-engine-cli.sh` — PASS
- `grep -q 'ANTIGRAVITY_API_KEY' .github/workflows/prevue-review.yml` — PASS
- `grep -Rq "script -qec" src/prevue/engines/cli_adapter.py` — PASS
- `grep -rL -- '--allow-tool' src/prevue/engines/cli_adapter.py` — PASS
- `bash scripts/ci-local.sh` — PASSED (800 passed, 0 failed; zizmor 0 new findings)

## Checkpoint: Task 3 — Live Antigravity sandbox verification

**Type:** `checkpoint:human-verify` (gate: blocking-human)

Task 3 is blocked on a live human verification of the Antigravity engine on a sandbox PR. This cannot be automated — the Antigravity CLI is a vendor-controlled binary with LOW-confidence non-TTY behavior. The checkpoint details are in the CHECKPOINT REACHED message returned by this executor.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_vendor_argv[antigravity-cli] assertion stale after pseudo-TTY implementation**
- **Found during:** Task 1 verification
- **Issue:** `test_vendor_argv` asserted `cmd[:2] == ["agy", "-p"]` but the pseudo-TTY wrapper changes the outer cmd to `["bash", "-c", "..."]`
- **Fix:** Updated assertion to check for `bash -c` wrapper form and `"script -qec"` in the shell command string
- **Files modified:** `tests/test_engine_contract.py`
- **Commit:** 1351dc6

**2. [Rule 1 - Bug] test_review_yml_named_secrets_no_inherit fails — dogfood review.yml missing antigravity-api-key**
- **Found during:** Task 1 ci-local.sh run
- **Issue:** `test_workflow_yaml.py` asserts all `workflow_call` secrets are present in the dogfood caller's `secrets:` block
- **Fix:** Added `antigravity-api-key: ${{ secrets.ANTIGRAVITY_API_KEY }}` to `review.yml`
- **Files modified:** `.github/workflows/review.yml`
- **Commit:** 1351dc6

**3. [Rule 1 - Bug] Ruff E501 line-too-long in new test assertions**
- **Found during:** Task 1 ci-local.sh run
- **Fix:** Split long f-string messages and ran `ruff format`
- **Files modified:** `tests/test_reusable_workflow_yaml.py`
- **Commit:** 1351dc6

**4. [Rule 1 - Bug] update-pricing.yml YAML parse error from multi-line git commit message in run: block**
- **Found during:** Task 2 actionlint check
- **Issue:** Multi-line git commit message with blank line inside YAML `run:` block caused YAML parse error
- **Fix:** Changed to single-line commit message; PR body written as shell variable to avoid YAML multi-line quoting issues
- **Files modified:** `.github/workflows/update-pricing.yml`
- **Commit:** c47af4e

**5. [Rule 1 - Bug] update-pricing.yml comments triggered the `! grep -qiE 'auto-merge|--auto'` acceptance gate**
- **Found during:** Task 2 acceptance verification
- **Issue:** Documentation comments saying "NEVER auto-merge" and "--auto flag" matched the grep gate
- **Fix:** Rewrote comments to use "never merged automatically" and removed "--auto flag" phrasing from comments
- **Files modified:** `.github/workflows/update-pricing.yml`
- **Commit:** c47af4e

## Known Stubs

None. The Antigravity engine is fully wired (install, secret, pseudo-TTY). The checkpoint (Task 3) exists precisely because this is the one unverifiable surface — vendor-controlled binary + non-TTY reliability. Token reporting for antigravity-cli correctly falls back to `estimated=True` (bytes/4) per Plan 03's `usage_capture="none"` spec field.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| mitigated: T-10-17 | .github/scripts/install-engine-cli.sh | Optional sha256sum gate for Antigravity install script; download-then-exec pattern |
| mitigated: T-10-18 | .github/workflows/update-pricing.yml | No merge step, no auto-approve — pricing bump requires human PR review |
| mitigated: T-10-19 | .github/workflows/update-pricing.yml | Explicit minimal permissions: contents:write + pull-requests:write only |
| mitigated: T-10-20 | .github/workflows/prevue-review.yml | ANTIGRAVITY_API_KEY gated on inputs.engine == 'antigravity-cli' |
| mitigated: T-10-21 | src/prevue/engines/cli_adapter.py | pseudo-TTY script -qec wrapper; empty output raises EngineFailure |

## Self-Check: PASSED

Files exist:
- .github/scripts/install-engine-cli.sh: FOUND (modified)
- .github/workflows/prevue-review.yml: FOUND (modified)
- .github/workflows/review.yml: FOUND (modified)
- .github/workflows/update-pricing.yml: FOUND (created)
- src/prevue/engines/cli_adapter.py: FOUND (modified)
- tests/test_reusable_workflow_yaml.py: FOUND (modified)
- tests/test_engine_contract.py: FOUND (modified)
- SECURITY.md: FOUND (modified)

Commits exist:
- 1351dc6: FOUND
- c47af4e: FOUND

---
*Phase: 10-boundary-contracts*
*Completed: 2026-06-29*
