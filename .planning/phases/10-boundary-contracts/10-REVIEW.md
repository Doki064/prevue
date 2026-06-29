---
phase: 10-boundary-contracts
reviewed: 2026-06-29T00:00:00Z
depth: standard
files_reviewed: 31
files_reviewed_list:
  - .github/scripts/install-engine-cli.sh
  - .github/workflows/prevue-review.yml
  - .github/workflows/review.yml
  - .github/workflows/update-pricing.yml
  - SECURITY.md
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
  - src/prevue/review.py
  - tests/conftest.py
  - tests/test_cli.py
  - tests/test_comments.py
  - tests/test_config_precedence.py
  - tests/test_engine_contract.py
  - tests/test_model_roles.py
  - tests/test_output_contract.py
  - tests/test_pricing.py
  - tests/test_raw_args.py
  - tests/test_registry.py
  - tests/test_reusable_workflow_yaml.py
  - tests/test_usage_capture.py
  - tests/test_workflow_yaml.py
findings:
  critical: 5
  warning: 4
  info: 3
  total: 12
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-29T00:00:00Z
**Depth:** standard
**Files Reviewed:** 31
**Status:** issues_found

## Summary

Phase 10 implements the ENGN-10 boundary-contract suite: declarative engine specs, a generic CLI adapter, per-role model resolution, usage capture strategies, pricing computation, versioned output, and workflow hardening for all four engines (copilot-cli, claude-code-cli, cursor-cli, antigravity-cli). The architecture is well-structured and the security posture (base-ref-only config, no `secrets: inherit`, SHA-pinned actions, no `--allow-tool`) is solid.

Five correctness and security defects were found: a documented `GEMINI_API_KEY` alias that is claimed to work but is never implemented; a false-zero suppression bug in the OTEL attribute extractor that silently drops zero-value token counts; a loose test assertion that lets the `classification.fallback.model` → `_resolve_engine_models` contract gap go undetected; an inline-comment update path that silently skips body refresh when severity has not changed; and a `gh pr create --label` failure that aborts the pricing bump PR when labels do not exist in the target repository. Four quality warnings were also found.

## Critical Issues

### CR-01: GEMINI_API_KEY alias documented but never implemented

**File:** `src/prevue/engines/spec.py:140-141`

**Issue:** The comment on the `antigravity-cli` spec entry states "GEMINI_API_KEY is accepted as an alias; consumer may also set GEMINI_API_KEY". `SECURITY.md` similarly documents this alias. However, `_build_env` in `cli_adapter.py` reads exactly `os.environ.get(spec.secret_env, "")`, which is `"ANTIGRAVITY_API_KEY"`. There is no fallback to `GEMINI_API_KEY` anywhere in the source tree. A consumer who sets only `GEMINI_API_KEY` (as documented) will receive an `AntigravityAuthError` and get no review — a silent, misleading failure that contradicts the published documentation.

**Fix:** Either implement the alias or remove the documentation. To implement:
```python
# In cli_adapter.py _build_env, after reading spec.secret_env:
raw_token = os.environ.get(spec.secret_env, "")
if not raw_token and spec.name == "antigravity-cli":
    raw_token = os.environ.get("GEMINI_API_KEY", "")
```
Or, add a `secret_env_aliases: tuple[str, ...] = ()` field to `CliEngineSpec` and loop over aliases in `_build_env`. Either way, the SECURITY.md / spec.py comments must match the code.

---

### CR-02: OTEL `_extract_attr_value` returns `None` for zero integer values, silently dropping valid token counts

**File:** `src/prevue/engines/usage.py:207-211`

**Issue:** `_extract_attr_value` uses chained `or` to select the first truthy value from the OTEL attribute value dict:
```python
return (
    value.get("intValue")
    or value.get("doubleValue")
    or value.get("stringValue")
    or value.get("boolValue")
)
```
When an `intValue` is `0` (e.g. zero cache-read tokens on a run with no cache hits), `value.get("intValue")` returns `0`, which is falsy, so the chain falls through to `doubleValue`, then `stringValue`, then `boolValue`, and finally returns `None`. The callers in `_parse_copilot_otel` then call `int(None)`, which raises `TypeError` — crashing the entire OTEL parse, falling back to `None` for the whole invocation, and reporting `estimated=True` for a Copilot run that actually had real OTEL data.

A secondary concern: `boolValue=False` would also be silently dropped, but token fields are integers so the zero-integer case is the live defect.

**Fix:**
```python
def _extract_attr_value(attr: dict[str, Any]) -> int | str | float | None:
    value = attr.get("value", {})
    if not isinstance(value, dict):
        return None
    for key in ("intValue", "doubleValue", "stringValue", "boolValue"):
        if key in value:
            return value[key]
    return None
```

---

### CR-03: `test_fallback_model_from_yml` assertion is vacuously true — the contract gap it was written to detect goes undetected

**File:** `tests/test_config_precedence.py:155-159`

**Issue:** The test passes `{"classification": {"fallback": {"model": "gpt-4o-mini"}}}` to `_resolve_engine_models`, intending to verify that `classification.fallback.model` feeds into the resolved classify-role model. However, `_resolve_engine_models` reads only the `engine` block and has no code that reads `classification.fallback.model` — that key is parsed separately in `load_config` into `FallbackConfig.model` and is applied at the call-site in `review.py` (line 608: `_effective_classify_model = _classify_model or fallback_cfg.model`). Since `raw` has no `engine` block, `_resolve_engine_models` returns `{"classify": None, "review": None, "consolidate": None}`. The assertion on line 159:
```python
assert "classify" in models or "fallback" in models or models.get("classify") == "gpt-4o-mini"
```
is satisfied by the first condition (`"classify" in models` is always `True`), so the test passes without verifying anything about `"gpt-4o-mini"`. The documented contract — that `classification.fallback.model` has any effect on the classify role through `_resolve_engine_models` — is not tested, and the integration path that actually wires it (`review.py:608`) has no direct test.

**Fix:** Correct the assertion to actually test the contract, or add a focused integration test through `run_review` that exercises the `fallback_cfg.model` path:
```python
# Tighten the assertion to what the contract actually promises:
# _resolve_engine_models does NOT read classification.fallback.model — that is
# applied at call-sites in review.py. The test must be rewritten to test either:
# (a) that models["classify"] is None when no engine.models.classify is set, OR
# (b) an integration test that run_review passes fallback_cfg.model to llm_classify
assert models.get("classify") is None  # no engine block → None from _resolve_engine_models
# And add a separate test that load_config populates fallback.model correctly:
raw2 = {"classification": {"fallback": {"model": "gpt-4o-mini"}}}
cfg = load_config_from_dict(raw2)
assert cfg.fallback.model == "gpt-4o-mini"
```

---

### CR-04: Inline comment body is not updated when severity has not changed — stale body silently persists

**File:** `src/prevue/github/comments.py:869-875`

**Issue:** In `post_inline_review`, an existing inline comment at `(path, line, side)` is added to `to_update` only when `_inline_severity_changed` returns `True`. When severity has not changed but the finding's title or body text has changed (engine rephrased the finding), the comment body is never updated:
```python
prior_comments = existing.get(key, [])
if prior_comments:
    prior = prior_comments[0]
    if _inline_severity_changed(prior.body or "", finding.severity):
        to_update.append((prior, body, finding))
    # ...
    continue   # ← always continues even if body text changed
```
The `continue` at line 875 skips `to_create` for this location regardless. The effect: an engine that rephrases a finding (different title, same severity, same location) leaves the old inline comment body intact on the PR while the sticky summary shows the new phrasing — a persistent inconsistency that misleads reviewers. This is distinct from the intended rephrase-at-same-line contract (which governs the open-set), because it concerns the live rendered inline comment content.

**Fix:**
```python
if prior_comments:
    prior = prior_comments[0]
    new_body = render_inline_comment(finding)
    if prior.body != new_body:          # update on any body change, not just severity
        to_update.append((prior, new_body, finding))
    if len(prior_comments) > 1:
        to_delete.extend(prior_comments[1:])
    continue
```

---

### CR-05: `update-pricing.yml` uses `--label "automated,pricing"` which fails when labels do not exist in the repository

**File:** `.github/workflows/update-pricing.yml:87`

**Issue:** The `gh pr create` invocation passes `--label "automated,pricing"`. GitHub's `gh pr create` will fail with a non-zero exit code when either label does not exist in the repository, causing the entire `Open pull request for human review` step to fail. Because the workflow does not use `|| true` or conditional label application, the pricing PR is never opened — silently defeating the automated bump mechanism. This is particularly risky for repositories that have not pre-created these labels, which is the majority of repositories that would consume or dogfood Prevue.

**Fix:**
```yaml
- name: Open pull request for human review
  if: steps.diff.outputs.changed == 'true'
  env:
    GH_TOKEN: ${{ github.token }}
    BRANCH: ${{ steps.commit.outputs.branch }}
  run: |
    TODAY=$(date +%Y-%m-%d)
    # Ensure labels exist before applying them (gh label create is idempotent with --force)
    gh label create "automated" --color "0075ca" --force || true
    gh label create "pricing" --color "e4e669" --force || true
    gh pr create \
      --title "chore: bump LiteLLM pricing snapshot ($TODAY)" \
      --body "$PR_BODY" \
      --head "$BRANCH" \
      --base main \
      --label "automated,pricing"
```

## Warnings

### WR-01: `filter_diff` uses `match_file` while all other pathspec callers use `check_file().include`

**File:** `src/prevue/classify/filter.py:22`

**Issue:** The entire codebase uses `GitIgnoreSpec.check_file(path).include` for glob matching (`classifier.py`, `pack.py`, `skills/loader.py`, `skills/selection.py`, `review.py`). `filter_diff` is the sole outlier, using `spec.match_file(f.path)`. The two APIs have different semantics for negation patterns (lines starting with `!`): `match_file` returns `True` for files matched positively, ignoring negation context in the same spec, whereas `check_file().include` correctly handles negation. If a consumer adds a negation exclude glob (e.g. `!**/*.generated.py`) to `ignore_globs`, `match_file` would silently ignore the negation and still drop the file, while the rest of the pipeline would correctly include it. This is an inconsistency that will produce surprising results at a consumer's first negation-glob attempt.

**Fix:** Change line 22 to use the same API as the rest of the codebase:
```python
if spec.check_file(f.path).include:
    dropped.append(f)
```

---

### WR-02: `_extract_attr_value` may trigger `TypeError` in `_parse_copilot_otel` when `intValue` is 0

**File:** `src/prevue/engines/usage.py:183-185`

**Issue:** (Secondary to CR-02.) Even if `_extract_attr_value` is fixed, the callers on lines 183–185 call `int(attrs.get(..., 0) or 0)`. When `attrs.get(key)` returns `None` (key absent), `None or 0` gives `0` — safe. But when `_extract_attr_value` (as currently written) returns `None` for a zero `intValue`, the `attrs` dict contains `{key: None}`. Then `attrs.get(key, 0)` returns `None`, and `None or 0` gives `0` — accidentally correct but masking the extraction failure. The real defect is the `TypeError` path: if `_extract_attr_value` returns a string (from `stringValue`) for a token field, `int("1200")` works, but `int(None)` or `int("abc")` would crash the try block, falling back to `None` for the whole file. The outer `try/except OSError` on line 187 does not catch `TypeError` or `ValueError` from `int()` — those would propagate uncaught out of `_parse_copilot_otel`.

**Fix:** Add `(TypeError, ValueError)` to the inner `try/except` around the span attribute walk, or guard each `int()` call:
```python
try:
    total_input += int(attrs.get(_OTEL_PROMPT_TOKENS, 0) or 0)
    total_output += int(attrs.get(_OTEL_COMPLETION_TOKENS, 0) or 0)
    total_cache_read += int(attrs.get(_OTEL_CACHE_READ_TOKENS, 0) or 0)
except (TypeError, ValueError):
    continue  # skip malformed span, T-10-07
```

---

### WR-03: `raw_args` are injected by mutating `engine._raw_args` post-construction — bypasses constructor invariants and is fragile

**File:** `src/prevue/review.py:572-573`

**Issue:** After `require_functional_adapter` returns a `CliEngineAdapter`, the code mutates the private `_raw_args` attribute directly:
```python
if not adapter and config.engine_config.raw_args and hasattr(engine, "_raw_args"):
    engine._raw_args = list(config.engine_config.raw_args)
```
This bypasses the constructor, relies on a naming convention (`hasattr`), and creates a hidden coupling between `review.py` and `CliEngineAdapter`'s internal field name. If the attribute is renamed or the adapter is initialized differently (e.g. through a future factory), this mutation silently becomes a no-op and `raw_args` from `prevue.yml` are silently dropped. The `hasattr` guard means the bug is silent — no error if the attribute disappears.

**Fix:** Expose `raw_args` through the adapter's constructor or a dedicated setter, then call it explicitly:
```python
# In cli_adapter.py, add a method:
def set_raw_args(self, raw_args: list[str]) -> None:
    self._raw_args = list(raw_args)

# In review.py:
if not adapter and config.engine_config.raw_args:
    engine.set_raw_args(config.engine_config.raw_args)
```

---

### WR-04: `update-pricing.yml` workflow uses `persist-credentials: true` on an `ubuntu-latest` runner with `contents: write`

**File:** `.github/workflows/update-pricing.yml:24`

**Issue:** The pricing bump workflow checks out with `persist-credentials: true` (the default when omitted, but explicitly set here). Combined with `contents: write` at the workflow level and git commands that push to the repository, this is appropriate for the intended use — but `persist-credentials: true` leaves the GITHUB_TOKEN credential cached in the git config on the runner's working directory for the entire job lifetime. While this is standard for push workflows, it is inconsistent with the hardening pattern in `prevue-review.yml` which explicitly sets `persist-credentials: false` on both checkouts. If additional steps are ever added to the pricing workflow (e.g. running arbitrary tooling), the credential remains accessible.

**Fix:** Explicitly set `persist-credentials: false` and use the `GH_TOKEN` env var (already set) for the push step instead:
```yaml
- uses: actions/checkout@...
  with:
    persist-credentials: false

# In the commit step, use git credential via GH_TOKEN:
- name: Commit and push pricing snapshot update
  env:
    GH_TOKEN: ${{ github.token }}
  run: |
    git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/${{ github.repository }}"
    ...
    git push origin "$BRANCH"
```

## Info

### IN-01: `gemini_cli.py` is misleadingly named — the file now contains `AntigravityAuthError`, not Gemini

**File:** `src/prevue/engines/gemini_cli.py:1`

**Issue:** The file was originally the Gemini skeleton, now repurposed for Antigravity (D-12). The module docstring and `__all__` export `AntigravityAuthError`, but the file is still named `gemini_cli.py`. This creates confusion when tracing imports: a developer looking at `from prevue.engines.gemini_cli import AntigravityAuthError` would not expect an Antigravity type there. The `__all__ = ["AntigravityAuthError"]` in a file called `gemini_cli` is actively misleading.

**Fix:** Rename to `antigravity_cli.py` (already the natural name following the pattern of `copilot_cli.py`, `claude_code_cli.py`, `cursor_cli.py`). Update all imports. Keep a `gemini_cli.py` shim that re-exports from `antigravity_cli` with a deprecation warning for any external consumers.

---

### IN-02: `_is_prevue_sticky` uses `lstrip()` before `_MARKER_RE.search` but tests `match.start() != 0`

**File:** `src/prevue/github/comments.py:673-675`

**Issue:** The `lstrip()` call strips leading whitespace from the comment body before the regex search, so `match.start() == 0` checks whether the marker is at position zero of the stripped body. This correctly handles comments with leading whitespace. However, `render_body` always emits the marker as the very first line (no leading whitespace), making the `lstrip()` redundant in practice. The inconsistency between `_is_prevue_sticky` (which lstrips before checking start position) and `parse_marker_sha` (line 75, which searches the raw body without lstrip) means the two functions behave differently on a body with leading whitespace — `_is_prevue_sticky` would accept it while `parse_marker_sha` would return `None`. This is a latent inconsistency that could surface if the bot ever emits a leading-whitespace body.

**Fix:** Either apply `lstrip()` in both functions (consistent) or remove it from `_is_prevue_sticky` and document that the marker must be the first character.

---

### IN-03: `test_vendor_argv` for `antigravity-cli` only checks `cmd[:2]` — does not assert that the prompt reaches the subprocess via `_AGY_PROMPT`

**File:** `tests/test_engine_contract.py:144-154`

**Issue:** The test verifies that the Antigravity adapter invokes via `bash -c` and that `"agy"` and `"script -qec"` appear in the shell command string. It does not assert that the actual prompt content was delivered to the engine. If the `_AGY_PROMPT` env var injection were broken (e.g., prompt set to `""` or the wrong variable name used), the test would still pass. The Cursor adapter has a stronger test (`test_cursor_model_mapping_and_prompt_file`) that reads the tempfile and asserts prompt content.

**Fix:** Extend the test to capture and assert `_AGY_PROMPT` from the subprocess env:
```python
elif engine_name == "antigravity-cli":
    assert cmd[:2] == ["bash", "-c"]
    shell_cmd = cmd[2]
    assert "agy" in shell_cmd
    assert "script -qec" in shell_cmd
    # Assert the prompt was delivered via the env var
    captured_env = kwargs.get("env") or {}
    assert "_AGY_PROMPT" in captured_env
    assert len(captured_env["_AGY_PROMPT"]) > 0
```

---

_Reviewed: 2026-06-29T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
