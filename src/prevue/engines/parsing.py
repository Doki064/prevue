"""Engine-agnostic prose+fence parser and strict per-finding salvage (ENGN-03, D-01/D-03)."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from prevue.models import Finding

FENCE_RE = re.compile(r"```json\s*\n(.*?)\n\s*```", re.DOTALL)


def extract_json_fence(stdout: str) -> tuple[str, list | None, str | None]:
    """Return (prose_without_fence, parsed_list_or_None, error_or_None)."""
    matches = list(FENCE_RE.finditer(stdout))
    if not matches:
        return stdout, None, "no ```json fence found in engine output"
    last = matches[-1]
    prose = stdout
    for match in reversed(matches):
        prose = prose[: match.start()] + prose[match.end() :]
    prose = prose.strip()
    try:
        payload = json.loads(last.group(1))
    except json.JSONDecodeError as e:
        return prose, None, f"JSON parse error: {e}"
    if not isinstance(payload, list):
        return prose, None, "top-level JSON value must be an array of findings"
    return prose, payload, None


def validate_findings(items: list) -> tuple[list[Finding], int]:
    """Keep valid findings, drop invalid; return (valid, dropped_count)."""
    valid: list[Finding] = []
    dropped = 0
    for item in items:
        try:
            valid.append(Finding.model_validate(item, strict=True))
        except ValidationError:
            dropped += 1
    return valid, dropped
