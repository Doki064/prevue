---
status: partial
phase: 10-boundary-contracts
source: [10-VERIFICATION.md]
started: 2026-06-29T12:00:00Z
updated: 2026-06-30T11:10:00Z
---

## Current Test

[testing complete — 1 blocked test (no COPILOT_GITHUB_TOKEN) keeps status partial]

## Tests

### 1. Live Antigravity sandbox review end-to-end
expected: |
  In sandbox, set engine: antigravity-cli, provide ANTIGRAVITY_API_KEY. Open a test PR.
  Confirm: sticky summary posted with findings, ~est token label, cost line renders,
  prevue-result.json artifact uploaded, compact job outputs populated.
result: issue
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
result: issue
reported: "User: 'I also said I want real token usage for all possible engines, and
  cursor is definitely possible (if not, look at Tokscale). This is absolutely a gap
  and need to be logged immediately.' No _parse_cursor_json function exists; cursor-cli
  always reports estimated=True regardless of CLI capability."
severity: major

## Summary

total: 4
passed: 1
issues: 2
pending: 0
skipped: 0
blocked: 1

## Gaps

- truth: "Antigravity CLI authenticates headlessly via ANTIGRAVITY_API_KEY/GEMINI_API_KEY in CI"
  status: failed
  reason: "Official docs indicate no non-interactive auth mode exists; spec.py's secret_env assumption (A1, low-confidence citation) may be structurally wrong"
  severity: major
  test: 1
  artifacts: []
  missing: []

- truth: "cursor-cli reports real (non-estimated) token usage when the CLI exposes it"
  status: failed
  reason: "usage_capture hardcoded to 'none' in spec.py with no Cursor envelope parser implemented; stale research finding never re-verified against installed CLI version"
  severity: major
  test: 4
  artifacts: []
  missing: ["_parse_cursor_json function in prevue/engines/usage.py", "usage_capture=\"stdout-json\" or equivalent on cursor-cli spec entry"]
