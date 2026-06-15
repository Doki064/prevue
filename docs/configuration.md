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
