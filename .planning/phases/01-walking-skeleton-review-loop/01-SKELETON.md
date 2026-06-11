# Walking Skeleton — Prevue

**Phase:** 1
**Generated:** 2026-06-12

## Capability Proven End-to-End

A pull request opened against a Prevue-enabled repository triggers an Actions run that fetches the diff via the GitHub API (no checkout of PR code), runs the GitHub Copilot CLI headless through the pluggable `EngineAdapter`, and posts one sticky summary comment that is updated in place on subsequent pushes — all under the `pull_request`-only trust model.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language / packaging | Python 3.12 floor (run 3.13), `uv init --package prevue`, `src/prevue/` layout, commit `uv.lock` | User constraint; matches `ubuntu-latest` default; `uv sync --locked` is fast, reproducible CI install (STACK.md) |
| Adapter contract | pydantic v2 model pair `ReviewRequest` → `ReviewResult` (with `findings: list[Finding]`) behind `EngineAdapter(ABC)` | Locked final ENGN-01 shape now (D-02); Phase 4 fills findings without reshaping models |
| Engine | GitHub Copilot CLI `@github/copilot` pinned `1.0.60`, headless `copilot -p ... -s --no-ask-user`, invoked via stdlib `subprocess` | First adapter; no wrapper SDK exists or is needed (STACK.md, ENGN-02) |
| Engine tools | **Zero** `--allow-tool` — diff passed inline in the prompt as fenced UNTRUSTED DATA | Strongest prompt-injection posture (Pattern 2); agent has no shell/write/exfil path |
| GitHub I/O | PyGithub 2.9.1 only (`Github(auth=Auth.Token(...))`); PR context from `GITHUB_EVENT_PATH` + `GITHUB_REPOSITORY`; diff via `pr.get_files()` (hunks only, D-08) | No `git` clone of untrusted code (DIFF-01 / SECR-01); deterministic Python owns all writes |
| Sticky comment | Hidden-marker upsert `<!-- prevue:sticky -->`, find-then-edit-or-create; sectioned shell Verdict/Review/Metadata (Verdict states "no verdict in v1") | One comment always current (OUTP-01, D-04/D-05/D-06) |
| Trigger / trust | `on: pull_request` ONLY (never `pull_request_target`); `permissions: { contents: read, pull-requests: write }`; pinned action SHAs; `concurrency` cancel-in-progress; fork detection + documented unsupported | Trust boundary is the skeleton's identity (SECR-01, Pitfalls 1/2/7) |
| Failure model | Engine error / timeout (300s) / empty output → raise → non-zero exit; sticky comment left untouched; no error comment on PR | Fail-closed, visible run failure (D-09/D-10) |
| Workflow shape | Thin workflow, fat CLI — YAML only does setup-uv → `uv sync` → `npm i -g @github/copilot@1.0.60` → one `uv run prevue review` | Logic testable in Python, not YAML (Pattern P4) |
| Testing | pytest + pytest-cov + `responses` (mock GitHub REST); monkeypatch `subprocess.run`; TDD for all clean-I/O units; live paths via spike + sandbox PR | TDD mode ON; live auth/subprocess not unit-mockable (D-11/D-12) |

## Stack Touched in Phase 1

- [x] Project scaffold — `uv` package, pyproject, ruff, pytest, `ci.yml`
- [x] Routing / entrypoint — `prevue review` CLI invoked by `on: pull_request` workflow
- [x] Real GitHub API read — `fetch_diff()` builds `DiffBundle` via `pr.get_files()` (no checkout)
- [x] Real engine call — `CopilotCliAdapter.review()` shells out to `copilot` on a live runner
- [x] Real GitHub API write — `upsert_sticky()` posts/updates one PR comment
- [x] Dev/CI run — `uv run prevue review` exercised by the wrapper workflow + sandbox PR (D-11)

## Artifacts This Phase Produces (full inventory)

| File | Symbols |
|---|---|
| `src/prevue/models.py` | `ChangedFile`, `DiffBundle`, `ReviewRequest`, `Finding`, `ReviewResult` |
| `src/prevue/engines/base.py` | `EngineAdapter` (ABC: `name`, `review()`) |
| `src/prevue/engines/copilot_cli.py` | `CopilotCliAdapter`, `CopilotAuthError`, `EngineFailure`, `_build_prompt`, `review` |
| `src/prevue/github/client.py` | `load_pr_context`, authenticated-PR resolver (`get_pull`) |
| `src/prevue/github/diff.py` | `fetch_diff` → `DiffBundle` |
| `src/prevue/github/comments.py` | `MARKER`, `render_body`, `upsert_sticky` |
| `src/prevue/review.py` | `run_review` orchestration (fetch → adapt → post), fork guard, D-09 failure handling |
| `src/prevue/cli.py` | `main` / `prevue review` entrypoint |
| `.github/workflows/` | `spike-copilot.yml` (throwaway), `review.yml` (wrapper), `ci.yml` |
| root | `pyproject.toml`, `uv.lock`, `README.md` (trigger matrix + token recipe), `tests/` + fixtures |

## Out of Scope (Deferred to Later Slices)

Explicit — prevents later phases from re-litigating Phase 1's minimalism:

- Classification / path filters / labels (Phase 2: DIFF-02, CLSF-01/03, ROUT-01)
- Skill bundle loading (Phase 3: SKIL-01/02/04)
- Structured findings, inline comments, severity, comment budget, pass/fail check (Phase 4: ENGN-03, OUTP-02/03, NOIS-02/03) — `findings` stays `[]`
- `workflow_call` packaging, consumer config, LLM classification fallback, skip conditions (Phase 5)
- Consumer custom skills, prompt-injection red-team, token transparency, large-PR budget (Phase 6)
- PR title/body in prompts (excluded permanently as instructions, D-07); full-file context fetching (D-08); fork PR support

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: deterministic classifier + routing (zero-token labels)
- Phase 3: selective SKILL.md bundle loading from trusted base ref
- Phase 4: schema-validated findings → position-validated inline comments + merge-gate check
- Phase 5: `workflow_call` packaging + hybrid LLM classification + consumer config (first shippable)
- Phase 6: consumer custom skills + prompt-injection verification + token transparency + large-PR budget
