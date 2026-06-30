---
status: partial
phase: 10-boundary-contracts
source: [10-VERIFICATION.md]
started: 2026-06-29T12:00:00Z
updated: 2026-06-30T11:57:37Z
---

## Current Test

[testing complete — gaps 1 and 4 resolved by gap-closure plan 10-07; 1 blocked test (no COPILOT_GITHUB_TOKEN) keeps status partial]

## Tests

### 1. Live Antigravity sandbox review end-to-end
expected: |
  In sandbox, set engine: antigravity-cli, provide ANTIGRAVITY_API_KEY. Open a test PR.
  Confirm: sticky summary posted with findings, ~est token label, cost line renders,
  prevue-result.json artifact uploaded, compact job outputs populated.
result: resolved
reported: "Per official Antigravity CLI docs (antigravity.google/docs/cli/install), no
  API-key / non-interactive auth mode exists. spec.py declares secret_env=ANTIGRAVITY_API_KEY
  (validate_secret checks it nonempty, AntigravityAuthError raised if absent) based on a
  LOW-confidence third-party citation (antigravitylab.net) in 10-RESEARCH.md Assumption A1.
  If the official docs are correct, the agy CLI cannot authenticate headlessly in CI under
  any value of this env var — the entire antigravity-cli engine (D-12, ENGN-10) is
  non-functional in production despite functional=true. This is exactly the risk A1 flagged
  as needing checkpoint:human-verify; no credential fixes it if the auth mechanism itself
  doesn't exist."
severity: major
resolution: "Gap-closure plan 10-07 flipped antigravity-cli to functional=False — require_functional_adapter now fails closed with NonFunctionalEngineError instead of shipping the unconfirmed headless-auth assumption as functional=true. get_adapter still resolves it (no install/invoke regression). Verified live in 10-VERIFICATION.md re-verification (commits 9f34db1..4dbe3b1)."

### 2. Copilot OTEL WARNING-3 real-token spot-check
expected: |
  Run engine: copilot-cli on sandbox. Sticky Tokens line shows WITHOUT ~est label
  (estimated=False), confirming COPILOT_OTEL_FILE_EXPORTER_PATH wiring enables real
  OTEL capture in CI.
result: blocked
blocked_by: third-party
reason: "No COPILOT_GITHUB_TOKEN available in this session to set as a sandbox repo secret."

### 3. Cursor-cli live review end-to-end (output contract)
expected: |
  cursor-cli review on test-sandbox-repo posts sticky summary with findings, cost line
  renders (or omits cleanly if no price match), ~est token label, prevue-result.json
  artifact uploaded, compact job outputs populated.
result: pass
notes: |
  PR #12 (Doki064/test-sandbox-repo, branch uat/phase10-cursor-output-contract).
  Sticky comment posted with 1 error + 1 warning findings, inline comments at
  src/api/checkout.py:28 and :20, "Tokens: review ~est 1508" (estimated=True
  correctly shown — usage_capture=none is correct-by-design for cursor-cli,
  cost line correctly omitted since model="default" has no pricing match (A4
  honest-no-cost behavior, not a bug). prevue/review check run conclusion=failure
  (correct per min_severity_to_fail: error in .github/prevue.yml). Artifact
  "prevue-result" (1055 bytes) downloaded and verified: schema_version="1.0",
  findings[] with path/line/side/severity/title/body/suggestion, engine_meta.tokens
  {review:1508, estimated:true}, per_call[]. Job outputs schema_version + error_count
  confirmed set via $GITHUB_OUTPUT in logs.

### 4. Cursor-cli real-token capture gap
expected: |
  Cursor CLI's `--output-format json` envelope should expose real token usage where
  the CLI supports it (third-party tools, e.g. Tokscale, extract real Cursor token
  counts from current cursor-cli versions). prevue.engines.spec.py hardcodes
  cursor-cli's usage_capture="none", and prevue.engines.usage.capture_usage dispatches
  "none" straight to `return None` — there is NO parser implemented for Cursor's
  envelope at all, unlike Copilot (_parse_copilot_otel) and Claude Code
  (_parse_stdout_json). 10-RESEARCH.md's finding ("Cursor's --output-format json
  returns no token fields — open feature request") was taken as final and never
  re-verified against the installed cursor-cli version before being locked into spec.py.
result: resolved
reported: "User: 'I also said I want real token usage for all possible engines, and
  cursor is definitely possible (if not, look at Tokscale). This is absolutely a gap
  and need to be logged immediately.' No _parse_cursor_json function exists; cursor-cli
  always reports estimated=True regardless of CLI capability."
severity: major
resolution: "Gap-closure plan 10-07 fixed the confirmed bug: cursor-cli now requests --output-format json (was text) and routes through usage_capture=stdout-json, reusing the proven Claude envelope-unwrap path. The token-fields claim is now a verified fact (official Cursor CLI docs confirm the json envelope has no usage fields) — estimated=True remains correct, but via the now-correct code path instead of the disconnected none strategy. junhoyeo/tokscale reads Cursor's web billing API via a manual session-cookie export, not cursor-agent stdout, so no further gap exists. Verified live in 10-VERIFICATION.md re-verification (commits 9f34db1..4dbe3b1)."

## Summary

total: 4
passed: 1
issues: 0
resolved: 2
pending: 0
skipped: 0
blocked: 1

## Gaps

Both gaps below are resolved by gap-closure plan 10-07 (commits 9f34db1..4dbe3b1); kept for audit trail.

- truth: "Antigravity CLI authenticates headlessly via ANTIGRAVITY_API_KEY/GEMINI_API_KEY in CI"
  status: resolved
  reason: "Official docs indicate no non-interactive auth mode exists; spec.py's secret_env assumption (A1, low-confidence citation) may be structurally wrong"
  root_cause: |
    spec.py's secret_env="ANTIGRAVITY_API_KEY" + GEMINI_API_KEY alias fallback (cli_adapter.py
    _build_env, ~line 65-66) was a design-time bet on an unverified, low-confidence third-party
    citation (antigravitylab.net — domain itself looks suspect vs official antigravity.google).
    10-RESEARCH.md flagged this exact risk (A1) and gated it behind a checkpoint:human-verify
    (10-06-SUMMARY.md Task 3) — that checkpoint was never closed, so the engine shipped as
    functional=true on an unconfirmed auth assumption. Not a code logic bug; a closed-loop
    verification step that never ran.
  severity: major
  test: 1
  artifacts:
    - src/prevue/engines/spec.py (antigravity-cli entry, secret_env field)
    - src/prevue/engines/cli_adapter.py (_build_env GEMINI_API_KEY alias fallback)
  missing:
    - "Live verification of agy CLI's actual non-interactive auth support (API key vs OAuth-only)"
    - "Startup smoke-test (e.g. agy --version / dry-run) to fail fast with actionable error before full review invocation"

- truth: "cursor-cli reports real (non-estimated) token usage when the CLI exposes it"
  status: resolved
  reason: "usage_capture hardcoded to 'none' in spec.py with no Cursor envelope parser implemented; stale research finding never re-verified against installed CLI version"
  root_cause: |
    Two-layer issue. (1) Confirmed bug independent of CLI capability: spec.py:128 invokes
    cursor-agent with --output-format text, not json — so even if Cursor's JSON envelope
    exposes token fields, prevue never requests it. (2) Unconfirmed: 10-RESEARCH.md's "no
    token fields" finding (line 335, dated 2026-06-28, sourced cursor.com/docs +
    forum.cursor.com) was never re-verified against the currently pinned cursor-agent
    version (install-engine-cli.sh curl-installs latest, no version pin). User's Tokscale
    citation (junhoyeo/tokscale, per 10-CONTEXT.md) documents Claude JSONL usage + Codex
    token_count as confirmed sources — does NOT list Cursor in its own description, so it
    may read a separate Cursor usage/billing API rather than cursor-agent stdout. Needs
    live verification before concluding which layer is the real gap.
  severity: major
  test: 4
  artifacts:
    - src/prevue/engines/spec.py:128 (cursor-cli base_argv uses --output-format text)
    - src/prevue/engines/usage.py:66-74 (capture_usage dispatcher, "none" branch)
  missing:
    - "Live check: does `cursor-agent -p --output-format json` (current version) expose token fields?"
    - "Check junhoyeo/tokscale source for its actual Cursor token-read mechanism (if any)"
    - "_parse_cursor_json function in prevue/engines/usage.py (only if JSON envelope confirmed to expose tokens)"
    - "usage_capture=\"stdout-json\" or new literal on cursor-cli spec entry + --output-format json in base_argv"
