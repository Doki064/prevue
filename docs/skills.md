# Custom Skills

Add review skills under `.github/prevue/skills/<bundle>/<name>.md` on your default branch.

## Override built-ins

Same `bundle/filename` as a built-in skill replaces it (e.g. `security/committed-secrets.md`).

## Add alongside

New filenames in an existing or new bundle directory add skills without removing built-ins.

## Revert an override

Delete the consumer file — the built-in skill loads again (D-06).

## Disable a skill

In `.github/prevue.yml`:

```yaml
skills:
  exclude:
    - security/committed-secrets.md
```

Exact `bundle/filename` keys (not globs).

## Caps

```yaml
skills:
  max_skill_bytes: 65536
  max_total_consumer_bytes: 262144
  max_consumer_skills: 50
```

Over-cap skills are skipped and disclosed in the review summary; malformed skills fail the run.

## Frontmatter

Each skill requires YAML frontmatter with `name`, `description`, and `applies-to` (glob list). See built-in skills in the Prevue repo for examples.
