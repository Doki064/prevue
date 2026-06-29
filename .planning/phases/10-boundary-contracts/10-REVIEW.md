---
phase: 10-boundary-contracts
reviewed: 2026-06-29T12:00:00Z
depth: standard
files_reviewed: 36
files_reviewed_list:
  - .github/scripts/install-engine-cli.sh
  - .github/workflows/prevue-review.yml
  - .github/workflows/review.yml
  - .github/workflows/update-pricing.yml
  - src/prevue/config.py
  - src/prevue/engines/claude_code_cli.py
  - src/prevue/engines/cli_adapter.py
  - src/prevue/engines/copilot_cli.py
  - src/prevue/engines/cursor_cli.py
  - src/prevue/engines/errors.py
  - src/prevue/engines/flow.py
  - src/prevue/engines/gemini_cli.py
  - src/prevue/engines/registry.py
  - src/prevue/engines/spec.py
  - src/prevue/engines/tokens.py
  - src/prevue/engines/usage.py
  - src/prevue/github/comments.py
  - src/prevue/pricing/__init__.py
  - src/prevue/pricing/model_prices.json
  - src/prevue/review.py
  - tests/fixtures/pricing/sample_prices.json
  - tests/fixtures/usage/antigravity_text.txt
  - tests/fixtures/usage/claude_envelope.json
  - tests/fixtures/usage/copilot_otel.jsonl
  - tests/fixtures/usage/cursor_envelope.json
  - tests/test_comments.py
  - tests/test_config_precedence.py
  - tests/test_copilot_adapter.py
  - tests/test_engine_contract.py
  - tests/test_model_roles.py
  - tests/test_output_contract.py
  - tests/test_pricing.py
  - tests/test_raw_args.py
  - tests/test_registry.py
  - tests/test_reusable_workflow_yaml.py
  - tests/test_usage_capture.py
findings:
  critical: 5
  warning: 5
  info: 3
  total: 13
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-29T12:00:00Z
**Depth:** standard
**Files Reviewed:** 36
**Status:** issues_found

## Narrative Findings (AI reviewer)

### Summary

Phase 10 delivers the boundary-contracts layer: declarative engine specs, a generic CLI adapter, per-role model resolution, usage capture strategies, pricing computation, versioned machine-readable output, and workflow hardening for all four engines. The security posture (base-ref-only config, SHA-pinned actions, no `secrets: inherit`, no `--allow-tool`) is sound. However, five correctness blockers were found.

The most damaging defect is a contradiction between Claude Code CLI's invocation flags and its usage-capture strategy: the spec calls `claude --output-format text` (plain text output) while `usage_capture="stdout-json"` instructs the engine layer to parse a JSON envelope. In production, `_parse_stdout_json` will fail on every Claude Code invocation, silently falling back to `estimated=True` bytes/4 — real token counts and vendor cost are never captured for Claude Code. A second blocker covers `emit_machine_output` being called only from the successful-review path, leaving `$GITHUB_OUTPUT` and `PREVUE_RESULT_FILE` empty on all skip and noop outcomes — downstream automation chains on job outputs will see empty strings. Additional blockers cover: a silent inline-comment body-refresh gap (unchanged-severity findings are never re-rendered even when text changes), a false-zero suppression bug in the OTEL extractor that can corrupt token counts, and the complete `compute_cost` pricing pipeline being dead code — fully implemented and tested but never called from the operational path.

---

## Critical Issues

### CR-01: Claude Code CLI invokes `--output-format text` but `usage_capture="stdout-json"` — real token capture permanently broken

**File:** `src/prevue/engines/spec.py:115-119`

**Issue:** The claude-code-cli spec declares:
```python
base_argv=("claude", "-p", "--output-format", "text"),
...
usage_capture="stdout-json",
```
With `--output-format text`, Claude Code emits unstructured plain text to stdout. The `usage_capture="stdout-json"` flag tells `capture_usage` to call `_parse_stdout_json`, which does `json.loads(stdout)` — this always raises `JSONDecodeError` for plain text, the function returns `None`, and `flow.py` falls back to `estimated=True` bytes/4 for every Claude Code review. Real token counts (input, output, cache tokens) and `cost_usd` from Claude's `total_cost_usd` field are never captured in production.

The `test_usage_capture.py::test_claude_stdout_json` and `test_usage_capture.py::test_claude_stdout_json_fence_extraction_pitfall3` tests pass because they inject a pre-built JSON envelope directly as `stdout` — bypassing the subprocess invocation and therefore the `--output-format text` mismatch. The `test_engine_contract.py::test_vendor_argv` test even asserts `cmd == ["claude", "-p", "--output-format", "text"]`, locking in the broken value.

The `_resolve_fence_source` guard in `flow.py:265` is correctly implemented for `stdout-json` engines — it exists precisely for this scenario. Switching the output format to `json` would make the entire capture path function as designed.

**Fix:**
```python
# src/prevue/engines/spec.py
CliEngineSpec(
    name="claude-code-cli",
    ...
    base_argv=("claude", "-p", "--output-format", "json"),  # was "text" — json gives usage envelope
    prompt_delivery="stdin",
    ...
    usage_capture="stdout-json",
    functional=True,
),
```
Also update `test_engine_contract.py:136` to assert `"json"` not `"text"`, and update `SECURITY.md:25` which documents the invocation as `claude --bare -p --output-format text` (the `--bare` flag is also absent from the spec but is separately documented in the comment on spec.py:109).

---

### CR-02: `emit_machine_output` only called from the full-review success path — `$GITHUB_OUTPUT` and `PREVUE_RESULT_FILE` are empty on all skip and noop outcomes

**File:** `src/prevue/review.py:1296`

**Issue:** `emit_machine_output` is invoked exactly once, at line 1296, at the bottom of the full-review success path. Every early-return path never calls it:

- `_publish_skip` (called at lines 502, 550, 566, 683, 781, 865, 942, 1049) — returns without writing output
- `_finish_noop_review` (lines 519, 529–539) — returns without writing output
- The fork guard return at line 480

Consequences:
1. The job output keys declared in `prevue-review.yml` (`schema_version`, `conclusion`, `error_count`, `warning_count`, `info_count`, `tokens`, `cost_usd`) are never written to `$GITHUB_OUTPUT` on skip/noop outcomes — downstream jobs reading `needs.review.outputs.conclusion` receive an empty string.
2. `PREVUE_RESULT_FILE` (`${{ runner.temp }}/prevue-result.json`) is never created on those paths. The artifact-upload step uses `if-no-files-found: warn`, so it produces a warning rather than surfacing the gap.
3. Downstream automation that branches on `conclusion == 'success'` or `conclusion == 'neutral'` will always take the falsy branch on skip/noop, silently suppressing any gating or alerting logic.

**Fix:** Call `emit_machine_output` from `_publish_skip` and `_finish_noop_review` with a minimal synthetic result:
```python
# In _publish_skip, add before the final return (after conclude_skip_check):
from prevue.models import ReviewResult  # already imported at module level
_skip_result = ReviewResult(summary_markdown=reason or "skipped")
emit_machine_output(_skip_result, conclusion)

# In _finish_noop_review, add after conclude_review_check succeeds:
emit_machine_output(noop_result, gate.conclusion)
```
`emit_machine_output` is defined later in the same module so it is already accessible.

---

### CR-03: `post_inline_review` silently drops body refresh when severity is unchanged — stale inline comment text persists indefinitely

**File:** `src/prevue/github/comments.py:869-875`

**Issue:** The upsert loop over `gate.inline` only adds a finding to `to_update` when `_inline_severity_changed` returns `True`. When severity is unchanged but the finding's title or body text has changed (engine rephrased the finding), the comment is silently skipped — neither queued for update nor for creation:

```python
if prior_comments:
    prior = prior_comments[0]
    if _inline_severity_changed(prior.body or "", finding.severity):
        to_update.append((prior, body, finding))
    if len(prior_comments) > 1:
        to_delete.extend(prior_comments[1:])
    continue   # always continues — body change without severity change is lost
```

The `continue` at line 875 fires whether or not the body was queued. An engine that rephrases a finding (different title, same severity, same location) leaves the old inline comment intact on the PR while the sticky summary shows the new phrasing — a persistent inconsistency. This is distinct from the intended rephrase-at-same-line open-set contract (which governs sticky dedup), because it governs the live inline comment content.

**Fix:**
```python
if prior_comments:
    prior = prior_comments[0]
    new_body = render_inline_comment(finding)
    # Update on any content change, not just severity change
    if prior.body != new_body:
        to_update.append((prior, new_body, finding))
    if len(prior_comments) > 1:
        to_delete.extend(prior_comments[1:])
    continue
```
The `to_update` tuple currently carries `(prior, body, finding)` — `body` was already the rendered body at line 866, so passing `new_body` is equivalent.

---

### CR-04: `_extract_attr_value` returns `None` for `intValue=0` — silently drops valid zero token counts and can cause `TypeError` crash

**File:** `src/prevue/engines/usage.py:207-211`

**Issue:** `_extract_attr_value` uses chained `or` to select among OTEL attribute value types:
```python
return (
    value.get("intValue")
    or value.get("doubleValue")
    or value.get("stringValue")
    or value.get("boolValue")
)
```
When `intValue` is `0` (a legitimate value — e.g., `cache_read_tokens=0` on a run with no cache hits), `value.get("intValue")` returns `0`, which is falsy. Python evaluates the next alternative. If all others are absent, the expression returns `None`. The caller then does:
```python
total_input += int(attrs.get(_OTEL_PROMPT_TOKENS, 0) or 0)
```
When `attrs[key]` is `None` (the extraction returned `None` for a zero-value field), `None or 0` gives `0` — accidentally correct but hiding the failure.

The more serious risk: if `_extract_attr_value` returns a non-integer type (e.g., a string from `stringValue` for a token field with a malformed OTEL record), `int(value)` raises `TypeError` or `ValueError`. The outer `try/except OSError` at line 187 does not catch `TypeError` — a malformed span attribute would propagate uncaught, aborting the whole OTEL parse and falling back to `None` (estimated=True).

**Fix:**
```python
def _extract_attr_value(attr: dict[str, Any]) -> int | str | float | bool | None:
    """Extract the scalar value from an OTEL attribute value dict."""
    value = attr.get("value", {})
    if not isinstance(value, dict):
        return None
    # Use explicit key presence check — `or` suppresses falsy values (0, False, "")
    for key in ("intValue", "doubleValue", "stringValue", "boolValue"):
        if key in value:
            return value[key]
    return None
```
And guard the `int()` calls:
```python
try:
    total_input += int(attrs.get(_OTEL_PROMPT_TOKENS) or 0)
    total_output += int(attrs.get(_OTEL_COMPLETION_TOKENS) or 0)
    total_cache_read += int(attrs.get(_OTEL_CACHE_READ_TOKENS) or 0)
except (TypeError, ValueError):
    continue  # skip malformed span (T-10-07)
```

---

### CR-05: `compute_cost` and the pricing pipeline are dead code — never called from the operational path

**File:** `src/prevue/pricing/__init__.py` (entire module), `src/prevue/config.py:124`

**Issue:** `compute_cost` and `load_pricing_table` are fully implemented (168 lines), covered by 8 passing tests, and wired into the config model (`EngineConfig.pricing: dict | None`). However, no module in the operational pipeline imports or calls `compute_cost`:

- `review.py` does not import `prevue.pricing`
- `flow.py` does not call `compute_cost` after `capture_usage`
- `usage.py` does not import pricing
- `cli_adapter.py` does not import pricing

The `cost_usd` that appears in the sticky comment (via `token_meta`) comes only from `_parse_stdout_json`'s `total_cost_usd` extraction — populated only for Claude Code, and only when the JSON envelope is parsed correctly (which is broken per CR-01). For all other engines, `cost_usd` is always `None` despite the pricing table existing. The `engine.pricing` override documented as D-06c is parsed from `prevue.yml` into `EngineConfig.pricing` but has no call site to consume it — the override is silently ignored.

The comment in `comments.py:550` states "compute_cost formula; None means unknown model" implying the formula is in use, which is false.

**Fix:** Wire `compute_cost` into `flow.py` inside `review_with_retry`, after `capture_usage` returns a non-None dict and `cost_usd` is absent from it. This requires passing the engine name, model label, and pricing override into the function. Minimal integration point:
```python
# In flow.py, after: captured = capture_usage(spec, raw_stdout, otel_path=otel_path)
if captured is not None and "cost_usd" not in captured and model_label and model_label != "default":
    from prevue.pricing import compute_cost
    priced = compute_cost(spec.name, model_label, captured, override=None)
    if priced is not None:
        captured["cost_usd"] = priced
```
The `override` (from `EngineConfig.pricing`) needs to be threaded through `review_with_retry`'s signature or resolved at the adapter level.

---

## Warnings

### WR-01: `GEMINI_API_KEY` alias documented but never implemented — consumers who set it receive `AntigravityAuthError` with no explanation

**File:** `src/prevue/engines/spec.py:140-141`

**Issue:** The comment states "GEMINI_API_KEY is accepted as an alias; primary var is ANTIGRAVITY_API_KEY." The workflow comment at `prevue-review.yml:143` repeats this claim. However, `_build_env` in `cli_adapter.py` reads only `os.environ.get(spec.secret_env, "")` — which is `"ANTIGRAVITY_API_KEY"`. There is no code anywhere that falls back to `GEMINI_API_KEY`. A consumer who sets `GEMINI_API_KEY` and not `ANTIGRAVITY_API_KEY` receives `AntigravityAuthError: ANTIGRAVITY_API_KEY is not set.` with no indication that the documented alias was supposed to work.

**Fix:** Either implement the alias in `_build_env`:
```python
raw_token = os.environ.get(spec.secret_env, "")
if not raw_token and spec.name == "antigravity-cli":
    raw_token = os.environ.get("GEMINI_API_KEY", "")
```
Or remove the alias claim from all comments and documentation.

---

### WR-02: `update-pricing.yml` uses `--label "automated,pricing"` without ensuring labels exist — PR creation silently fails

**File:** `.github/workflows/update-pricing.yml:87`

**Issue:** `gh pr create --label "automated,pricing"` exits non-zero when either label does not exist in the repository, causing the step to fail. The pricing update branch is then committed and pushed but no PR is opened — the automated bump mechanism fails silently. This will affect every repository that does not pre-create these labels (i.e., all fresh repositories).

**Fix:**
```bash
# Ensure labels exist (gh label create --force is idempotent)
gh label create "automated" --color "0075ca" --description "Automated change" --force || true
gh label create "pricing"   --color "e4e669" --description "Pricing data"     --force || true
gh pr create \
  --title "$PR_TITLE" \
  --body "$PR_BODY" \
  --head "$BRANCH" \
  --base main \
  --label "automated,pricing"
```

---

### WR-03: `update-pricing.yml` branch name collision — same-day re-runs push to an existing branch and fail

**File:** `.github/workflows/update-pricing.yml:52`

**Issue:** The branch name `chore/update-pricing-$(date +%Y%m%d)` is date-based. If the workflow runs twice on the same day (via `workflow_dispatch` after a failure, or if the schedule fires while a prior run is still open), `git push origin "$BRANCH"` fails because the remote branch already exists. The `commit` step exits non-zero, leaving the branch uncommitted and no PR opened.

**Fix:**
```bash
BRANCH="chore/update-pricing-$(date +%Y%m%d)"
# Delete stale same-day remote branch if it exists (idempotent re-run)
git push origin --delete "$BRANCH" 2>/dev/null || true
git checkout -b "$BRANCH"
```

---

### WR-04: `raw_args` injection in `review.py` mutates `_raw_args` directly — bypasses constructor and is fragile

**File:** `src/prevue/review.py:572-573`

**Issue:**
```python
if not adapter and config.engine_config.raw_args and hasattr(engine, "_raw_args"):
    engine._raw_args = list(config.engine_config.raw_args)
```
This mutates a private attribute post-construction via `hasattr` duck-typing. If `_raw_args` is ever renamed or the adapter is constructed differently, the `hasattr` guard means the mutation silently becomes a no-op — `raw_args` from `prevue.yml` is dropped with no error. This violates encapsulation and creates a hidden coupling.

**Fix:** Expose `raw_args` through a named constructor parameter or a public setter on `CliEngineAdapter`:
```python
# In cli_adapter.py, add a method:
def set_raw_args(self, raw_args: list[str]) -> None:
    self._raw_args = list(raw_args)

# In review.py:
if not adapter and config.engine_config.raw_args:
    engine.set_raw_args(config.engine_config.raw_args)
```

---

### WR-05: `test_fallback_model_from_yml` assertion is vacuously true — the contract it is meant to test is not verified

**File:** `tests/test_config_precedence.py:155-159`

**Issue:** The test passes `{"classification": {"fallback": {"model": "gpt-4o-mini"}}}` to `_resolve_engine_models`, intending to verify that `classification.fallback.model` flows into the classify role model. However, `_resolve_engine_models` only reads the `engine` block — it has no code that reads `classification.fallback.model`. The function returns `{"classify": None, "review": None, "consolidate": None}`. The assertion:
```python
assert "classify" in models or "fallback" in models or models.get("classify") == "gpt-4o-mini"
```
is satisfied by the first clause (`"classify" in models` is always `True`), so the test passes while testing nothing about `"gpt-4o-mini"`. The actual integration path (`review.py:608: _effective_classify_model = _classify_model or fallback_cfg.model`) has no direct test.

**Fix:** Correct the assertion to reflect what `_resolve_engine_models` actually promises for this input:
```python
# _resolve_engine_models does NOT read classification.fallback.model
# Assert the actual behavior: no engine block → all roles resolve to None
models = _resolve_engine_models(raw)
assert models.get("classify") is None
# Add a separate test for the load_config + fallback.model integration:
cfg = load_config(str(cfg_file_with_fallback_model))
assert cfg.fallback.model == "gpt-4o-mini"
```

---

## Info

### IN-01: `gemini_cli.py` exports `AntigravityAuthError` — module name contradicts its contents (D-12 rename incomplete)

**File:** `src/prevue/engines/gemini_cli.py:1`

**Issue:** The file was originally the Gemini skeleton and was repurposed for Antigravity per D-12. The module docstring and `__all__` now export `AntigravityAuthError`, but the file is still named `gemini_cli.py`. This contradicts the pattern of every other engine module (`copilot_cli.py`, `claude_code_cli.py`, `cursor_cli.py`). Developers tracing imports from `from prevue.engines.gemini_cli import AntigravityAuthError` would be confused.

**Fix:** Rename to `antigravity_cli.py` to match the engine-module naming convention. Keep a `gemini_cli.py` shim that re-exports from `antigravity_cli` for any external consumers, with a deprecation note. Update all internal imports.

---

### IN-02: `_is_prevue_sticky` and `parse_marker_sha` behave differently on bodies with leading whitespace — latent inconsistency

**File:** `src/prevue/github/comments.py:673-675`

**Issue:** `_is_prevue_sticky` calls `lstrip()` before `_MARKER_RE.search` and checks `match.start() != 0`. `parse_marker_sha` (line 75) searches the raw body without `lstrip()`. On a comment body with leading whitespace, `_is_prevue_sticky` would accept it as a valid sticky (because the marker is at position 0 after stripping), but `parse_marker_sha` would return `None` (no marker at the raw start). The result: the sticky would be identified and upserted but the last-reviewed SHA would be lost, causing the next run to treat it as first-run (full review instead of incremental). This is latent — `render_body` always produces a marker at position 0 with no leading whitespace — but fragile.

**Fix:** Apply consistent treatment: either strip in both functions or in neither.

---

### IN-03: `test_vendor_argv` for `antigravity-cli` does not assert prompt delivery via `_AGY_PROMPT`

**File:** `tests/test_engine_contract.py:144-154`

**Issue:** The test verifies that Antigravity uses `bash -c` and `script -qec`. It does not assert that the actual prompt was delivered via `_AGY_PROMPT` in the subprocess environment. If the env injection were broken (wrong variable name or empty string), the test would still pass. Cursor has a stronger equivalent (`test_cursor_model_mapping_and_prompt_file`) that reads the tempfile and asserts prompt content is present.

**Fix:** Capture the `env` kwarg in the mock and assert `_AGY_PROMPT` is set and non-empty:
```python
elif engine_name == "antigravity-cli":
    assert cmd[:2] == ["bash", "-c"]
    shell_cmd = cmd[2]
    assert "agy" in shell_cmd
    assert "script -qec" in shell_cmd
    env = captured.get("env") or {}
    assert "_AGY_PROMPT" in env and env["_AGY_PROMPT"]
```

---

_Reviewed: 2026-06-29T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
