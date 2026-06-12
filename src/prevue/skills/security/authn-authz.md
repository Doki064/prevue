---
name: Authentication & Authorization
description: Review changes to auth flows, session handling, and access control for privilege and bypass risks.
applies-to:
  - "**/auth/**"
  - "**/*auth*"
  - "**/middleware/**"
  - "**/*session*"
---
- Verify every new endpoint/handler enforces authentication and the correct authorization check (no missing guard).
- Check for broken access control: object-level authorization (IDOR), role checks done client-side only, or trusting user-supplied IDs.
- Session/token handling: secure + httpOnly cookies, expiry, rotation on privilege change, no tokens in URLs or logs.
- Confirm auth failures fail closed (deny by default), and error messages don't leak whether a user exists.
