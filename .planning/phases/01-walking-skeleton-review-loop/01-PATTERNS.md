# Phase 1: Walking Skeleton Review Loop - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 13 new (no modifications — greenfield)
**Analogs found:** 0 in-repo / 13 — **GREENFIELD: no application code exists**

> **Greenfield notice.** The repo contains only `LICENSE`, `.planning/`, and `.agents/skills/` tooling
> (the only `*.py` files are skill scripts under `.agents/skills/caveman-compress/scripts/`, NOT application
> code). There are **no in-repo analogs to copy**. Every file below is the *first* of its kind and
> **establishes** the convention later phases will mirror. The canonical sources are the prescriptive
> code examples already in `01-RESEARCH.md` plus `.planning/research/{STACK,ARCHITECTURE}.md`. Planner:
> copy patterns from the cited RESEARCH.md line ranges, not from any sibling file.

## File Classification

| New File | Role | Data Flow | Canonical Source (no in-repo analog) | Match |
|----------|------|-----------|--------------------------------------|-------|
| `src/prevue/models.py` | model (pydantic v2 contract) | transform / validation | `01-RESEARCH.md` §Pattern 1, lines 205–242 | establishes |
| `src/prevue/engines/base.py` | port (ABC) | request-response | `01-RESEARCH.md` §Pattern 1, lines 244–252 | establishes |
| `src/prevue/engines/copilot_cli.py` | adapter (engine) | request-response (subprocess) | `01-RESEARCH.md` §Adapter, lines 337–390 | establishes |
| `src/prevue/github/client.py` | service (auth/resolution) | request-response | `01-RESEARCH.md` §Diff Fetch, lines 314–318 (`load_pr_context`) | establishes |
| `src/prevue/github/diff.py` | service (fetch) | request-response (read) | `01-RESEARCH.md` §Diff Fetch, lines 308–333 | establishes |
| `src/prevue/github/comments.py` | service (write) | CRUD (upsert) | `01-RESEARCH.md` §Sticky Comment, lines 394–414 | establishes |
| `src/prevue/review.py` | orchestrator | request-response (pipeline) | `01-RESEARCH.md` §System Diagram, lines 141–173 (fetch→adapt→post) | establishes |
| `src/prevue/cli.py` | entrypoint (CLI) | request-response | thin-workflow/fat-CLI rule, lines 262, 439 (`uv run prevue review`) | establishes |
| `.github/workflows/review.yml` | config (CI trigger) | event-driven | `01-RESEARCH.md` §Workflow YAML, lines 418–443 | establishes |
| `.github/workflows/spike-copilot.yml` | config (throwaway spike) | event-driven | `01-RESEARCH.md` §Spike, lines 446–456 (D-12, run FIRST) | establishes |
| `.github/workflows/ci.yml` | config (CI tests) | event-driven | Sampling Rate, lines 542–552 (pytest+ruff+actionlint+zizmor) | establishes |
| `pyproject.toml` | config (uv package) | — | Installation, lines 113–121 (`uv init --package prevue`) | establishes |
| `tests/` (test_*.py + fixtures) | test | — | §TDD Units + Test Map, lines 517–539 | establishes |

## Patterns to Establish

These are the conventions Phase 1 sets for the whole codebase. State them once; later phases inherit.

### P1 — pydantic v2 adapter contract (the seam's data shape)
**Establishes for:** all cross-component I/O. **Source:** `01-RESEARCH.md` lines 205–242.
- v2 API only — `BaseModel`, `Field(default_factory=...)`, `str | None` unions. Never v1-style validators.
- `DiffBundle` deliberately carries **no PR title/body** field (D-07 injection posture — keep this absent).
- `Finding` exists now but `ReviewResult.findings` defaults `[]` (D-02); prose rides in `summary_markdown`.
- **Locked contract:** `ReviewRequest → ReviewResult` must not break in Phase 4. Phase 4 fills findings; it does not reshape the models.

### P2 — Ports-and-adapters engine seam
**Establishes for:** every future engine (Phase: more adapters). **Source:** lines 201–252, 254–257.
- `EngineAdapter(ABC)` with one `@abstractmethod review(self, req) -> ReviewResult` and a `name: str`.
- Adapter is the **only** component that knows an AI vendor exists. It returns a result; it **never** posts to GitHub.
- Concrete adapter (`CopilotCliAdapter`) shells out via stdlib `subprocess.run(..., timeout=, capture_output=True, text=True)` — no wrapper SDK.
- Auth guard runs **before** invocation (Pitfall 7): reject token unless `github_pat_` prefix; raise `CopilotAuthError`. Map every other failure (timeout / non-zero exit / empty stdout) → `EngineFailure` → non-zero exit (D-09/D-10). Define both exception types in `copilot_cli.py`.
- Prompt fences the diff as **UNTRUSTED DATA** and grants the agent **zero tools** (no `--allow-tool`).

### P3 — Deterministic Python owns all GitHub writes
**Establishes for:** all GitHub interaction. **Source:** lines 75, 261, 394–414.
- PyGithub only (`Github(auth=Auth.Token(...))`) — never raw `requests`. PR context from `GITHUB_EVENT_PATH` JSON + `GITHUB_REPOSITORY`, never a `git` clone (DIFF-01 / SECR-01).
- Diff via `pr.get_files()` → per-file `.patch` (hunks only, D-08); `patch=None` tolerated for large/binary files.
- Sticky comment = hidden-marker upsert: `MARKER = "<!-- prevue:sticky -->"`, iterate `pr.get_issue_comments()`, `c.edit()` if found else `pr.create_issue_comment()` (OUTP-01 / D-06). Never blind-create (no duplicate stacking).
- Sectioned body shell from day one: **Verdict / Review / Metadata**, Verdict states "no verdict in v1" (D-04/D-05).

### P4 — Thin workflow, fat CLI
**Establishes for:** all workflow YAML. **Source:** lines 262, 417–443.
- No logic in YAML. Workflow only: setup-uv → `uv sync --locked` → `npm i -g @github/copilot@1.0.60` → one `uv run prevue review`.
- `on: pull_request` **only** — never `pull_request_target` (Pitfall 1). Minimal `permissions: { contents: read, pull-requests: write }`. Pin action SHAs. `concurrency` group cancels superseded runs.
- Secrets enter only here: `GITHUB_TOKEN: ${{ github.token }}` (fetch/post) + `COPILOT_GITHUB_TOKEN: ${{ secrets.COPILOT_GITHUB_TOKEN }}` (engine). Never let `GITHUB_TOKEN` shadow the Copilot token (Pitfall 7).
- Fork guard: detect `head.repo.full_name != GITHUB_REPOSITORY`, exit early with documented message (Pitfall 2).

### P5 — uv-managed package layout
**Establishes for:** repo structure. **Source:** lines 113–121, 175–199.
- `uv init --package prevue`; `src/prevue/` layout; commit `uv.lock`. Sub-packages `github/` and `engines/` are import namespaces (`from prevue.models import ...`, `from prevue.engines.base import EngineAdapter`).
- Keep `src/prevue/` stage-aligned so later phases slot `classifier/`, `router/`, `skills/` packages in cleanly.

### P6 — TDD units with mocked boundaries
**Establishes for:** all tests. **Source:** lines 508–552.
- `pytest` + `pytest-cov`; mock GitHub REST with `responses` (PyGithub uses `requests`); monkeypatch `subprocess.run` for adapter failure paths. Fixtures: recorded `/pulls/{n}/files` payload + sample event JSON under `tests/fixtures/`.
- Test-first candidates: model validation/round-trip, `_build_prompt` (asserts diff+files present, PR title/body **absent**), failure→`EngineFailure`/auth-guard, sticky create-vs-edit, diff mapping incl. `patch=None`.
- Not unit-testable (live only): real Copilot auth/subprocess + real posting → spike (D-12) + wrapper workflow + sandbox repo (D-11).

## Shared Patterns (cross-cutting, apply to multiple files)

### Untrusted-input fencing (V5)
**Apply to:** `engines/copilot_cli.py::_build_prompt` (and any future prompt builder). Diff content is labelled DATA inside fences; PR title/body never enter the prompt. See lines 354–360.

### Failure → non-zero exit, comment untouched (D-09)
**Apply to:** `engines/copilot_cli.py`, `review.py`, `cli.py`. Engine errors raise; orchestrator does **not** reach `upsert_sticky`; process exits non-zero so the Actions run visibly fails. No error comments on the PR thread.

### Secret handling (V2/V7)
**Apply to:** adapter + workflows. Never log tokens; truncate `stderr` in error text (`proc.stderr[-500:]`); rely on Actions secret masking; no `set -x` around auth.

## No Analog Found

**All 13 files** — greenfield repo, no in-repo analog exists for any. Planner uses the RESEARCH.md prescriptive
examples (cited line ranges above) and `.planning/research/{STACK,ARCHITECTURE}.md` as the canonical source for every file.

## Metadata

**Analog search scope:** repo root (`**/*.py`, `src/`, `tests/`, `.github/workflows/`, `pyproject.toml`, `uv.lock`)
**Files scanned:** 7 Python files found — all under `.agents/skills/` tooling, none application code
**Pattern extraction date:** 2026-06-12
