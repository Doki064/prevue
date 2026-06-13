---
phase: 04-structured-findings-merge-gate
reviewed: 2026-06-13T05:27:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - pyproject.toml
  - src/prevue/engines/parsing.py
  - src/prevue/models.py
  - src/prevue/engines/copilot_cli.py
  - src/prevue/github/positions.py
  - src/prevue/gate.py
  - src/prevue/github/comments.py
  - src/prevue/github/checks.py
  - src/prevue/github/client.py
  - src/prevue/review.py
  - .github/workflows/review.yml
  - tests/test_findings_parsing.py
  - tests/test_positions.py
  - tests/test_gate.py
  - tests/test_checks.py
  - tests/test_copilot_adapter.py
  - tests/test_models.py
  - tests/test_comments.py
  - tests/test_review_flow.py
  - tests/test_workflow_yaml.py
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-06-13T05:27:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Iteration-3 removed previous workflow/config regressions. Review still finds one BLOCKER prompt-boundary escape path and two WARNING-grade output-safety gaps in markdown rendering and fenced diff handling.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Diff filename can break untrusted-data boundary in engine prompt

**File:** `src/prevue/engines/copilot_cli.py:94-109`
**Issue:** `_build_prompt()` embeds `f.path` raw inside the diff section (`### {f.path}`) that sits within `~~~UNTRUSTED DATA` fences. A crafted filename containing newline + `~~~` can terminate that block and inject attacker-controlled instructions into trusted prompt context. This is a prompt-injection boundary break in untrusted PR input handling.
**Fix:**
```python
def _safe_heading_path(path: str) -> str:
    # Keep path single-line and escaped before prompt insertion.
    return json.dumps(path, ensure_ascii=True)

hunks = "\n\n".join(
    f"path={_safe_heading_path(f.path)}\n{_safe_diff_block(f.patch)}"
    for f in req.diff.files
    if f.patch
)
```

## Warnings

### WR-01: Static four-backtick fence can be broken by diff content

**File:** `src/prevue/engines/copilot_cli.py:68-71`
**Issue:** `_safe_diff_block()` always uses ```` fences and only escapes triple backticks. If patch text contains a run of four backticks, the fence can terminate early and corrupt downstream prompt structure.
**Fix:**
```python
def _safe_diff_block(patch: str) -> str:
    runs = [len(m.group(0)) for m in re.finditer(r"`+", patch)]
    fence_len = max(4, (max(runs) + 1) if runs else 4)
    fence = "`" * fence_len
    return f"{fence}diff\n{patch}\n{fence}"
```

### WR-02: Sticky detail summary permits raw HTML injection from finding title

**File:** `src/prevue/github/comments.py:90-95`
**Issue:** `render_finding_details()` uses `_escape_table_cell()` for `<summary>` content, but that helper escapes pipes/newlines only. Raw `<`/`>` in model-generated titles can inject HTML fragments into sticky comment rendering, causing misleading or malformed output.
**Fix:**
```python
from html import escape

summary = escape(f"{finding.path}:{finding.line} — {finding.title}", quote=False)
blocks.append(
    f"<details><summary>{summary}</summary>\n\n"
    f"{render_inline_comment(finding)}\n"
    f"</details>"
)
```

---

_Reviewed: 2026-06-13T05:27:00Z_  
_Reviewer: Claude (gsd-code-reviewer)_  
_Depth: standard_
