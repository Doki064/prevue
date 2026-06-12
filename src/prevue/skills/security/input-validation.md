---
name: Input Validation & Injection
description: Review untrusted-input handling for injection and validation gaps.
applies-to:
  - "**/*.py"
  - "**/*.go"
  - "**/*.rb"
  - "**/*.java"
  - "**/*.ts"
  - "**/*.js"
---
- Parameterized queries / ORM for all SQL — flag string-concatenated queries (SQLi).
- Validate + bound all external input (size, type, range); reject by allowlist, not denylist.
- Shell/subprocess calls: no untrusted data in the command string; avoid `shell=True` with interpolation.
- Path handling: prevent traversal (`../`); resolve + confine to an allowed root.
- Deserialization of untrusted data uses safe loaders (e.g. `yaml.safe_load`, never `pickle` on untrusted input).
