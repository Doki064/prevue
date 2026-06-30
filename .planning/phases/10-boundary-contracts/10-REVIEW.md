---
phase: 10-boundary-contracts
reviewed: 2026-06-30T11:51:13Z
depth: standard
files_reviewed: 39
files_reviewed_list:
  - .github/scripts/install-engine-cli.sh
  - .github/workflows/prevue-review.yml
  - .github/workflows/review.yml
  - .github/workflows/update-pricing.yml
  - SECURITY.md
  - docs/configuration.md
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
  - tests/conftest.py
  - tests/fixtures/pricing/sample_prices.json
  - tests/fixtures/usage/antigravity_text.txt
  - tests/fixtures/usage/claude_envelope.json
  - tests/fixtures/usage/copilot_otel.jsonl
  - tests/fixtures/usage/cursor_envelope.json
  - tests/test_cli.py
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
  - tests/test_workflow_yaml.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-30T11:51:13Z
**Depth:** standard
**Files Reviewed:** 39
**Status:** issues_found

## Summary

This is the fourth review iteration of phase 10 (boundary contracts), following the
10-07 gap closure that (a) switched `cursor-cli` to `--output-format json` and routed
it through the `stdout-json` envelope-unwrap path, and (b) flipped `antigravity-cli` to
`functional=False`. Both of those specific changes are implemented correctly and are
well covered by tests: `_resolve_fence_source`/`capture_usage` correctly share the
Claude envelope parser for Cursor (`usage` block absent → graceful `None` → bytes/4
estimate, not a crash), `require_functional_adapter` correctly blocks antigravity-cli
from `run_review`, and the registry/contract test suites exercise both paths
end-to-end. The full test suite (795 tests) and `ruff check` both pass clean.

The defect found in this iteration is **not** in the gap-closure code itself, but in
documentation that the gap-closure work (and an earlier commit in the same phase,
`4e683b5`) silently desynced from the implementation. `SECURITY.md`'s D-08 trust-boundary
row and `docs/configuration.md`'s engine/secrets tables both describe stale CLI
invocations and a stale secret name for `claude-code-cli`, and `SECURITY.md` additionally
documents the pre-10-07 Cursor invocation. Because `SECURITY.md` is the canonical
document operators are told to consult before enabling merge-gate workflows (per its own
D-08 text and the `test_security_md_documents_d08_live_verification` test), shipping it
with incorrect invocation strings undermines the exact pre-production verification
process it exists to support.

## Critical Issues

### CR-01: SECURITY.md and docs/configuration.md document a secret name that does not exist in the workflow, breaking claude-code-cli for consumers who follow the docs

**File:** `SECURITY.md:25`, `docs/configuration.md:243,277,312`
**Issue:**
Both documents tell consumers that `claude-code-cli` requires `ANTHROPIC_API_KEY` /
`anthropic-api-key`:

```
docs/configuration.md:243: | `claude-code-cli` | Functional | `anthropic-api-key` | `ANTHROPIC_API_KEY` |
docs/configuration.md:277: | `anthropic-api-key` | No | `claude-code-cli` | Anthropic API key. Maps to `ANTHROPIC_API_KEY` |
docs/configuration.md:312: | `ANTHROPIC_API_KEY` | Engine-dependent | — | API key for `claude-code-cli` |
SECURITY.md:25: ... Claude: `claude --bare -p --output-format text`. ...
```

But the actual reusable workflow only declares and wires `claude-code-oauth-token` /
`CLAUDE_CODE_OAUTH_TOKEN`:

```
.github/workflows/prevue-review.yml:33:   claude-code-oauth-token:
.github/workflows/prevue-review.yml:142:  CLAUDE_CODE_OAUTH_TOKEN: ${{ inputs.engine == 'claude-code-cli' && secrets.claude-code-oauth-token || '' }}
```

and `src/prevue/engines/spec.py:112` reads `secret_env="CLAUDE_CODE_OAUTH_TOKEN"`. There
is no `anthropic-api-key` input anywhere in `prevue-review.yml`'s `workflow_call.secrets`
block, and no `ANTHROPIC_API_KEY` env var is ever set for the review step. A consumer who
follows the documented table and passes `secrets.anthropic-api-key: ...` to the reusable
workflow will get a silent no-op (the unknown secret name is simply not forwarded) and
`claude-code-cli` will always raise `ClaudeAuthError("CLAUDE_CODE_OAUTH_TOKEN is not
set.")` at review time — a hard failure for every PR using that engine.

This is a regression introduced within phase 10 itself: commit `4e683b5`
("fix(10-06): replace ANTHROPIC_API_KEY with CLAUDE_CODE_OAUTH_TOKEN for claude-code-cli")
updated the workflows, `spec.py`, `errors.py`, and 5 test files, but never touched
`docs/configuration.md` or `SECURITY.md`. The same root-cause bug also exists in
`.github/workflows/prevue-command-run.yml:91` (`ANTHROPIC_API_KEY: ... secrets.ANTHROPIC_API_KEY`),
which is outside this review's explicit file list but confirms the slash-command path
(`/prevue review`) is also broken for claude-code-cli, not just the docs.

Additionally, `SECURITY.md:25`'s Claude invocation string is stale on two counts: it says
`claude --bare -p --output-format text`, but the code (changed in the same `4e683b5`
commit) dropped `--bare` (which blocks `CLAUDE_CODE_OAUTH_TOKEN`) and now passes
`--output-format json` (`spec.py:115`: `base_argv=("claude", "-p", "--output-format", "json")`).

**Fix:**
Update `docs/configuration.md` (3 locations) to read `claude-code-oauth-token` /
`CLAUDE_CODE_OAUTH_TOKEN`:
```diff
- | `claude-code-cli` | Functional | `anthropic-api-key` | `ANTHROPIC_API_KEY` |
+ | `claude-code-cli` | Functional | `claude-code-oauth-token` | `CLAUDE_CODE_OAUTH_TOKEN` — long-lived token from `claude setup-token` |
```
```diff
- | `anthropic-api-key` | No | `claude-code-cli` | Anthropic API key. Maps to `ANTHROPIC_API_KEY` |
+ | `claude-code-oauth-token` | No | `claude-code-cli` | Long-lived OAuth token (`claude setup-token`). Maps to `CLAUDE_CODE_OAUTH_TOKEN` |
```
```diff
- | `ANTHROPIC_API_KEY` | Engine-dependent | — | API key for `claude-code-cli` |
+ | `CLAUDE_CODE_OAUTH_TOKEN` | Engine-dependent | — | OAuth token for `claude-code-cli` (`claude setup-token`) |
```
Update `SECURITY.md:25` to match the current invocation strings for both Claude and
Cursor (see WR-01 below — fix together since they're in the same sentence), and fix
`prevue-command-run.yml:90-91` to set `CLAUDE_CODE_OAUTH_TOKEN` from
`secrets.CLAUDE_CODE_OAUTH_TOKEN` (note: this file is outside this review's explicit
scope but shares the identical defect and should be fixed in the same pass).

## Warnings

### WR-01: SECURITY.md's D-08 trust-boundary row documents the pre-gap-closure Cursor invocation

**File:** `SECURITY.md:25`
**Issue:**
The D-08 vector table row states:

```
Cursor: `cursor-agent -p --output-format text -f`.
```

But the 10-07 gap closure (commit `432d1c7`, "feat(10-07): request real cursor-cli JSON
envelope (Gap A)") changed this to `--output-format json`
(`src/prevue/engines/spec.py:140`: `base_argv=("cursor-agent", "-p", "--output-format", "json")`).
This row is the canonical place SECURITY.md tells operators to verify against before a
live D-08 tool-posture check (per its own text: "**Live engine tool-posture verify
(D-08) is a required pre-production checkpoint** — run each adapter in a sandbox PR and
confirm no unexpected tool calls occur"). An operator following the documented string
would not be checking the actual flags the adapter sends.

The same row also says "Gemini adapter is a v1 skeleton (not invoked)" — Gemini was
replaced by Antigravity per D-12 (confirmed by `tests/test_registry.py::test_skeleton_engines_removed`
and `test_antigravity_cli_is_registered_but_not_functional`), so this sentence is also
stale and should instead describe Antigravity's `functional=False` status and the
`script -qec` pseudo-TTY wrapper it actually uses (`cli_adapter.py:160-197`).

**Fix:**
```diff
- Claude: `claude --bare -p --output-format text`. Cursor: `cursor-agent -p --output-format text -f`. Gemini adapter is a v1 skeleton (not invoked).
+ Claude: `claude -p --output-format json`. Cursor: `cursor-agent -p --output-format json -f`. Antigravity (`agy -p`) is registered but `functional=False` — `require_functional_adapter` rejects it before any subprocess runs; when it does run (future), invocation goes through a `script -qec` pseudo-TTY wrapper (see cli_adapter.py).
```

### WR-02: Cursor and Antigravity never get a computed cost even when bytes/4 estimation is available

**File:** `src/prevue/engines/flow.py:154-168, 205-221`
**Issue:**
`compute_cost` is only invoked inside the `if spec is not None:` branch that follows a
*successful* `capture_usage` call (`captured is not None`). For `cursor-cli`
(`usage_capture="stdout-json"` but no `usage` block in its real envelope) and
`antigravity-cli` (`usage_capture="none"`), `capture_usage` always returns `None`, so
`captured` stays `None` and the `compute_cost` block is skipped entirely — `cost_usd`
is never set, even though `_token_meta`'s bytes/4 `review_tokens` estimate could be fed
into `compute_cost` to give consumers an approximate dollar figure (labeled `~est`, the
same pattern already used for tokens). The sticky comment's `Cost:` line
(`comments.py:551-555`) silently omits cost for these two engines while still showing
estimated token counts, which is an inconsistent user-facing signal (tokens shown but
cost absent, with no stated reason).

This is pre-existing behavior, not introduced by the 10-07 gap closure, but the gap
closure is exactly what made Cursor's real-world behavior (`captured=None`) permanent
and confirmed/tested — the right moment to flag it.

**Fix:**
In `_token_meta`/`_retry_token_meta`, when `captured is None` but `model_label` is a
real model, call `compute_cost` with the bytes/4 `review_tokens` as `input`
(or document explicitly in the sticky output why Cursor/Antigravity cost is omitted, to
avoid an unexplained gap between the token and cost lines).

### WR-03: `docs/configuration.md`'s "Engine install versions" table omits antigravity-cli

**File:** `docs/configuration.md:249-255`
**Issue:**
The table lists only `copilot-cli`, `claude-code-cli`, and `cursor-cli`, but
`.github/scripts/install-engine-cli.sh:24-36` has a real, fully-implemented
`antigravity-cli)` install case (curl-fetched installer with optional SHA-256 pin). A
reader trying to understand what gets installed for `antigravity-cli` (e.g. to set
`PREVUE_ANTIGRAVITY_INSTALL_SHA256`, which is correctly documented elsewhere in
SECURITY.md) has to cross-reference the install script directly since this table is
silent on it.

**Fix:**
Add a row:
```diff
| `cursor-cli` | Official shell installer (`https://cursor.com/install`) | Not version-pinned — supply-chain risk; prefer `copilot-cli` or `claude-code-cli` where pinning matters |
+| `antigravity-cli` | Official shell installer (`https://antigravity.google/cli/install.sh`) | Not version-pinned; registered but `functional=False` — install only matters for future use |
```

## Info

### IN-01: `gemini_cli.py` filename no longer matches its content

**File:** `src/prevue/engines/gemini_cli.py:1-16`
**Issue:**
The module's only content is `AntigravityAuthError` re-exported "for import stability,"
with a docstring explaining "D-12: Gemini CLI replaced by Antigravity CLI." Keeping the
re-export for backward compatibility is reasonable, but the file's name (`gemini_cli.py`)
is itself confusing/misleading documentation debt — a reader searching for the Antigravity
adapter source would not find it under this filename, and `docs/ARCHITECTURE.md:100,191`
and `docs/DEVELOPMENT.md:179,303` (outside this review's explicit scope, but worth noting)
still reference `gemini_cli.py` / `GeminiAdapter` / `SKELETON_ENGINES`, all of which are
gone per `tests/test_registry.py::test_skeleton_engines_removed`.

**Fix:** Consider renaming to `antigravity_cli.py` with a deprecated re-export shim at
the old path only if any external consumer is known to import it directly (grep shows no
internal imports of `prevue.engines.gemini_cli` by name in `src/` or `tests/`), and update
`docs/ARCHITECTURE.md`/`docs/DEVELOPMENT.md` to drop `SKELETON_ENGINES`/Gemini references.

### IN-02: `EngineModels.consolidate` "reserved for Phase 13" comment is duplicated near-verbatim three times

**File:** `src/prevue/config.py:104, 266, 293`
**Issue:**
Not a defect, but the comment is duplicated nearly verbatim at the class docstring, the
function docstring, and the inline `_role("consolidate")` call site
(`# D-13: reserved; Phase 13 (QUAL-01) will consume it` /
`# D-13: reserved; consumed in Phase 13`). Minor duplication; if Phase 13 changes the
plan, three places need updating in lockstep instead of one.

**Fix:** Consolidate to a single docstring reference (e.g. only on the class) and have
the other two sites refer back to it (`# see EngineModels docstring`).

---

_Reviewed: 2026-06-30T11:51:13Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
