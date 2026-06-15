# Configuration

Consumer settings live in `.github/prevue.yml` on the trusted base ref.

## Review budget

```yaml
review:
  max_input_tokens: 120000   # default; ~480k bytes at bytes/4 heuristic
  output_reserve_tokens: 12000 # reserved for engine JSON output
  min_severity_to_comment: warning
  min_severity_to_fail: null
  max_inline_comments: 10
```

`max_input_tokens` stays under the ~250k-token stdin guard (`MAX_PROMPT_BYTES` / 4). Oversized PRs pack whole files by risk weight; skipped files are disclosed.

**Limitation — LLM-only paths under tight budgets:** Pack priority is computed from `labels` globs and skill `applies-to` *before* the LLM classification fallback runs. A file that no deterministic glob matches gets the lowest pack priority and is dropped first when over budget — so the LLM fallback (which might have flagged it security-relevant) never sees it. Under tight `max_input_tokens`, unrule-matched high-risk files can be silently excluded. Mitigation: add an explicit `labels` glob for security-sensitive path patterns (e.g. `**/auth/**`, `**/*secret*`) so they pack ahead of generic files, or raise the budget.

## Skills

```yaml
skills:
  exclude: []
  max_skill_bytes: 65536
  max_total_consumer_bytes: 262144
  max_consumer_skills: 50
```

See [skills.md](./skills.md).

## Classification fallback

```yaml
classification:
  fallback:
    enabled: true
    model: null
```

LLM classify runs only on unmatched paths **in the packed (reviewed) file set**.

## Engine

```yaml
engine:
  name: copilot-cli
```

Or set `PREVUE_ENGINE` in the workflow environment.

Unknown keys are rejected (`extra: forbid` on all sections).
