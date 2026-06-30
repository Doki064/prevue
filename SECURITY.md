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
| 4 | Engine tool reach (PR metadata / network) | Adapters invoke CLIs with **no `--allow-tool` flags** (code-audited). Copilot: `copilot -s --no-ask-user`. Claude: `claude --safe-mode -p --output-format json` — `--safe-mode` disables CLAUDE.md/skills/plugins/hooks/MCP-server auto-discovery without restricting auth to API-key-only (unlike `--bare`, which blocks `CLAUDE_CODE_OAUTH_TOKEN`); see T-08 note below. Cursor: `cursor-agent -p --output-format json -f`. Antigravity (`agy -p`) is registered but `functional=False` — `require_functional_adapter` rejects it before any subprocess runs; when it does run (future), invocation goes through a `script -qec` pseudo-TTY wrapper (see `cli_adapter.py`). **Live engine tool-posture verify (D-08) is a required pre-production checkpoint** — run each adapter in a sandbox PR and confirm no unexpected tool calls occur before enabling in merge-gate workflows. See the step-by-step checklist in [docs/consumer-setup.md](docs/consumer-setup.md#engine-tool-posture-check-before-merge-gates-d-08) and the 07-05 UAT checklist. |

**T-08 note (`--bare` vs `--safe-mode` tradeoff, 10-THERMOS):** `claude-code-cli` originally dropped `--bare` entirely because `--bare` strictly requires `ANTHROPIC_API_KEY`/`apiKeyHelper` auth and never reads OAuth/keychain, which would break `CLAUDE_CODE_OAUTH_TOKEN`-based CI auth. Running without `--bare` re-enabled CLAUDE.md/skills/plugin/hook/MCP auto-discovery, which caused 300s startup timeouts on headless Actions runners. `--safe-mode` resolves both: it disables the same startup-heavy auto-discovery `--bare` does, but (per `claude --help`) does not narrow the auth surface — OAuth/keychain auth still work. Re-evaluate if a future Claude Code CLI release changes `--safe-mode`'s auth behavior.

## SKIL-04: base-ref-only loading

Skills and config load from the trusted base ref (`PREVUE_CONSUMER_ROOT` / workflow base SHA), never from the PR head. A PR cannot inject skills into its own review in the same run.

## Consumer skill caps

Oversized consumer skills are skipped and disclosed. Skill load failures fail the review closed: `run_review` catches `ValidationError` (malformed frontmatter), `OSError` (unreadable file), `UnicodeDecodeError` (bad encoding), and `yaml.YAMLError` (invalid YAML syntax from `frontmatter.loads`), posts an explanatory PR comment via `upsert_skip_note`, publishes a `prevue/review` failure check run (`conclusion="failure"`), and returns — skill content never reaches the engine and the job always emits a structured failure signal.

## Antigravity CLI install-script trust (T-10-17 / D-12)

The Antigravity CLI (`agy`) is installed in-workflow via a curl-fetched install script from `https://antigravity.google/cli/install.sh`. The script is downloaded to `$RUNNER_TEMP` and executed — it is not piped directly to bash.

Consumers who want to pin a known-good install script can set the optional `PREVUE_ANTIGRAVITY_INSTALL_SHA256` workflow variable to the SHA-256 of the install script. When set, the workflow verifies the downloaded script with `sha256sum -c -` before executing it (mirroring the `PREVUE_CURSOR_INSTALL_SHA256` pattern for Cursor). Without the pin, the install proceeds with the latest script from the vendor — acceptable for development; recommended to pin for merge-gate workflows.

## LiteLLM pricing snapshot trust (SKIL-04 / D-06a / D-06b)

Prevue's cost computation uses a vendored copy of the LiteLLM pricing table (`src/prevue/pricing/model_prices.json`). This snapshot is **never fetched at review time** — pricing is read from the package, not the network. This eliminates runtime supply-chain risk for pricing data (SKIL-04 / D-06a).

When the snapshot needs updating, the scheduled `update-pricing.yml` workflow fetches the latest LiteLLM JSON, commits it to a branch, and opens a pull request. **The PR is never merged automatically** — a human must review the diff for unexpected schema changes or injected data before merging (D-06b / T-10-18).
