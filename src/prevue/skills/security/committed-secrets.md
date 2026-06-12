---
name: Committed Secrets & Credentials
description: Flag any secret, credential, token, private key, or password committed in the diff. Alert only — never redact or modify.
applies-to:
  - "**/*"
---
Scan added or modified lines for committed secrets and ALERT (do not redact):
- API keys, access tokens, bearer tokens, OAuth client secrets
- Private keys (`-----BEGIN ... PRIVATE KEY-----`), `.pem`, `.key`, `.p12`
- Passwords / connection strings with embedded credentials (`://user:pass@host`)
- Cloud credentials (AWS access key IDs `AKIA...`, GCP service-account JSON, Azure keys)
- High-entropy strings assigned to names like `token`, `secret`, `password`, `apikey`
- `.env` files or `.env.*` with real values (not placeholders)

For each: report file + line, name the credential type, and recommend rotation + removal from history. Treat hardcoded secrets as **error** severity. Do not echo the full secret value back in the comment — reference it by location.
