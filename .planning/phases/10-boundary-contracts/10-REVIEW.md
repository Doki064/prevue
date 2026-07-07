---
phase: 10-boundary-contracts
reviewed: 2026-07-06T07:00:00Z
depth: standard
files_reviewed: 32
files_reviewed_list:
  - .github/scripts/install-engine-cli.sh
  - .github/workflows/prevue-command-run.yml
  - .github/workflows/prevue-review.yml
  - .github/workflows/review.yml
  - .github/workflows/update-pricing.yml
  - docs/configuration.md
  - src/prevue/config.py
  - src/prevue/engines/cli_adapter.py
  - src/prevue/engines/errors.py
  - src/prevue/engines/flow.py
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
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 10: Code Review Report (re-review after 10-11 gap-closure)

**Reviewed:** 2026-07-06T07:00:00Z
**Depth:** standard
**Files Reviewed:** 32 (full phase scope); scrutiny concentrated on the 10-11 diff (`src/prevue/engines/cli_adapter.py`, `tests/test_copilot_adapter.py`)
**Status:** issues_found (no criticals; 1 warning, 1 info)

## Summary

This is a re-review after the 10-11 narrow gap-closure landed. The prior
`10-REVIEW.md` (pass 5) CR-01 (`update-pricing.yml` jq `null`-string bug) and
WR-01 (pricing-validator regression test gap) were both independently
re-confirmed fixed by the Thermos external review
(`10-THERMOS-REVIEW.md`: "Fixed" verdicts for both, with evidence citations),
so this pass does not re-litigate them.

The 10-11 diff itself: `otel_path` construction in `CliEngineAdapter.review()`
changed from `tempfile.mkdtemp(dir=base_otel_dir)` (pre-creates an empty
directory — confirmed via a real Copilot CLI 1.0.67 reproduction, recorded in
`.planning/debug/copilot-otel-real-capture-recurrence.md`, to silently no-op
the OTEL file exporter) to
`os.path.join(base_otel_dir, f"{uuid.uuid4().hex}.jsonl")` (constructs a
unique leaf path without touching the filesystem). This is a correct fix for
its stated goal: the leaf path is no longer pre-created as anything, the
matching `OSError` degrade path was correctly re-pointed at `os.makedirs` (the
only remaining filesystem call in this construction), the corresponding tests
were updated consistently (renamed, assertions flipped from
`os.path.isdir(p)` to `not os.path.exists(p)`, mock target moved from
`tempfile.mkdtemp` to `os.makedirs`), and `_parse_copilot_otel` already
handles both file and directory inputs so no parser change was needed. Full
targeted suite run: `tests/test_copilot_adapter.py` — 41 passed.

One accuracy gap survives the fix, exposed (not introduced) by the same root
cause the fix addresses: because the first and retry invocations inside a
single `review()` call share the exact same `otel_path` by design, and the
real Copilot exporter only writes a span file when the exact configured path
does not already exist, a retried Copilot call's own OTEL span is never
written — the first invocation's write occupies the path first. This degrades
safely through the existing `_otel_capture_grew` /
`_partial_estimate_retry_tokens` fallback (no crash, no corrupted totals), but
silently under-counts real usage/cost for every retried `otel-jsonl` review,
and no test anywhere in the suite exercises a retry against a populated
`otel_path` to confirm this specific fallback path is actually reached. See
WR-01 below.

A lightweight pattern scan (hardcoded secrets, `eval`/`exec`/shell-injection
primitives, debug artifacts, empty catches) across the rest of the listed
files found no new occurrences; those files were previously reviewed clean
and are unchanged by the 10-11 diff.

## Warnings

### WR-01: Retry invocation silently loses its own real OTEL capture — same `otel_path` reused; comment overstates "retry accounting is unaffected"

**File:** `src/prevue/engines/cli_adapter.py:222-227` (claim), `:236-260` (shared `otel_path` construction/closure)
**Also:** `src/prevue/engines/flow.py:478` (first invocation captures via this `otel_path`), `:537-539` (retry invocation re-parses the *same* `otel_path`), `:274-307` (`_otel_capture_grew`), `:310-348` (`_partial_estimate_retry_tokens`)

**Issue:** The comment at `cli_adapter.py:225-227` reads:

```python
# first + retry invocations of this same call still share one path
# (both use the same `env`/`otel_path` closure below), so retry accounting
# is unaffected.
```

Per the debug log's own THIRD-RECURRENCE finding
(`.planning/debug/copilot-otel-real-capture-recurrence.md:222-236`), the real,
CI-pinned Copilot CLI 1.0.67 file exporter "writes a single file AT the exact
configured path, creating it only if the path doesn't already exist." Because
the first invocation writes real span data to `otel_path`, by the time the
retry invocation runs (same `otel_path`, same `env`, same closure), the path
already exists — so the retry's own OTEL span is never written by the real
CLI. `flow.py`'s `_enrich_capture` call for the retry (`flow.py:537-539`)
re-parses the exact same file the first invocation wrote; it sees no growth,
`_otel_capture_grew` correctly returns `False`, and
`_partial_estimate_retry_tokens` kicks in — so nothing crashes and totals
aren't silently corrupted, but the retry's real token/cost contribution is
never captured, only bytes/4-estimated.

This is a genuine, reproducible-by-inspection asymmetry the comment does not
describe: before this fix, under the broken `tempfile.mkdtemp` code, *neither*
invocation ever got real capture (both always estimated), so "retry
accounting is unaffected" was accidentally true. Now the first invocation
does get real capture and the retry does not — a new, more subtle failure
mode than "always estimated," and one a future reader of this comment would
not expect.

Additionally, `_otel_capture_grew`'s docstring (`flow.py:278-291`) documents
only one cause of "no growth" — the retry falling back to stdin delivery past
`argv_prompt_max_bytes` — and does not mention this second, now more common
cause (same-path-already-exists). No test in `tests/test_copilot_adapter.py`
(`TestOtelPerCallIsolation`) or `tests/test_engine_flow.py` exercises a retry
with a populated `otel_path` (real or simulated file content written before
the second `invoke()` call) to confirm the fallback is actually reached for
this reason — every existing `TestOtelPerCallIsolation` test uses a mocked
`subprocess.run` that never writes to `otel_path` at all, so this exact
interaction is untested.

**Fix:** Give each `invoke()` call (first vs. retry) its own unique leaf
filename inside `base_otel_dir` instead of computing one `otel_path` per
`review()` call, and read usage by globbing `base_otel_dir` (the existing
`path.is_dir()` branch in `_parse_copilot_otel` already sums `*.jsonl` across
a directory) so both invocations' real spans are captured and summed:

```python
# Sketch: keep base_otel_dir (a directory) as the value passed to the
# subprocess env, and generate a fresh leaf filename per invoke() call
# instead of once per review() call, so first and retry never collide:
def _fresh_otel_leaf(base_dir: str) -> str:
    return os.path.join(base_dir, f"{uuid.uuid4().hex}.jsonl")
```

At minimum (if the directory-glob redesign is deferred), correct the
misleading comment to state the real, current limitation, and add a
regression test that pre-writes real JSONL content at the first invocation's
`otel_path` before the mocked retry runs, asserting
`engine_meta["tokens"]["estimated"] is True` and that the reported
input/output reflect the WR-02 partial-estimate blend (first real + retry
estimate) rather than implicitly claiming full real accounting for both
invocations.

## Info

### IN-01: Rest of file set unchanged since prior clean reviews — no new issues found

**Files:** all listed files other than `src/prevue/engines/cli_adapter.py` /
`tests/test_copilot_adapter.py`

These files were previously reviewed clean (10-REVIEW pass 5, since
re-verified fixed for its own findings, and the Thermos external review, both
zero-critical outcomes). A targeted pattern scan across this file list for
this pass found no new hardcoded secrets, dangerous-function usage, or debug
artifacts. No action needed here; the Thermos review's existing non-blocking
follow-ups (stale per-engine-adapter docs in `docs/DEVELOPMENT.md` /
`docs/TESTING.md`, `review.py` god-module size, classify/skill-select cost
omission from reported spend) remain open as previously tracked and are out of
scope for this narrow re-review.

---

_Reviewed: 2026-07-06T07:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
