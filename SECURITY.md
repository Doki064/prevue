# Prevue Security Model

## Trust boundary

| Zone | Trust level | Source |
|------|-------------|--------|
| Consumer config (`.github/prevue.yml`) | Trusted | Base ref checkout |
| Consumer skills (`.github/prevue/skills/`) | Trusted instructions | Base ref checkout only (SKIL-04) |
| PR diff hunks, paths, status | **Untrusted data** | GitHub API |
| Engine findings output | Untrusted until validated | Engine stdout |

PR title, body, and comments are **never** passed to review engines (DiffBundle excludes them).

Fork PRs are unsupported in v1. Workflows use `pull_request` only — not `pull_request_target`.

Findings may only reference lines present in the reviewed diff (position validation output-side guard).

## Untrusted vectors and mitigations

| # | Vector | Mitigation |
|---|--------|------------|
| 1 | Diff hunk content | 4-backtick diff fences, backtick escaping, `UNTRUSTED DATA` blocks, `INSTRUCTION_REASSERTION` tail |
| 2 | File paths / status | JSON-escaped paths, fenced `UNTRUSTED DATA`, reassertion tail |
| 3 | Classify fallback prompt | `build_classify_prompt` fences paths; reassertion tail |
| 4 | Engine tool reach (PR metadata / network) | Adapters invoke CLIs with **no `--allow-tool` flags** (code-audited). Copilot: `copilot -s --no-ask-user`. Claude: `claude --bare -p --output-format text`. Cursor: `cursor-agent -p --output-format text -f`. Gemini adapter is a v1 skeleton (not invoked). **Live engine tool-posture verify (D-08) is a required pre-production checkpoint** — run each adapter in a sandbox PR and confirm no unexpected tool calls occur before enabling in merge-gate workflows. See the step-by-step checklist in [docs/consumer-setup.md](docs/consumer-setup.md#engine-tool-posture-check-before-merge-gates-d-08) and the 07-05 UAT checklist. |

## SKIL-04: base-ref-only loading

Skills and config load from the trusted base ref (`PREVUE_CONSUMER_ROOT` / workflow base SHA), never from the PR head. A PR cannot inject skills into its own review in the same run.

## Consumer skill caps

Oversized consumer skills are skipped and disclosed. Skill load failures fail the review closed: `run_review` catches `ValidationError` (malformed frontmatter), `OSError` (unreadable file), `UnicodeDecodeError` (bad encoding), and `yaml.YAMLError` (invalid YAML syntax from `frontmatter.loads`), posts an explanatory PR comment via `upsert_skip_note`, publishes a `prevue/review` failure check run (`conclusion="failure"`), and returns — skill content never reaches the engine and the job always emits a structured failure signal.
