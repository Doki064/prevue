"""Shared helpers for engine adapter tests."""

from __future__ import annotations

import json

from prevue.models import ChangedFile, DiffBundle, ReviewRequest

VALID_TOKEN = "github_pat_0123456789abcdefghijklmnopqrstuvwxyz"
PROSE_REVIEW = "## Review\n\nLooks good overall."

VALID_FINDING = {
    "path": "src/main.py",
    "line": 3,
    "side": "RIGHT",
    "severity": "warning",
    "title": "Unused import",
    "body": "Remove the unused import.",
}


def stdout_with_fence(*, prose: str = PROSE_REVIEW, payload: object | None = None) -> str:
    body = json.dumps([] if payload is None else payload)
    return f"{prose}\n\n```json\n{body}\n```"


def make_sample_request(
    *, instructions: str = "Review this pull request carefully."
) -> ReviewRequest:
    return ReviewRequest(
        diff=DiffBundle(
            pr_number=42,
            base_sha="base000",
            head_sha="head111",
            files=[
                ChangedFile(
                    path="src/main.py",
                    status="modified",
                    additions=3,
                    deletions=1,
                    patch="@@ -1,3 +1,4 @@\n def main():\n+    pass\n     return 0",
                ),
                ChangedFile(
                    path="README.md",
                    status="added",
                    additions=10,
                    deletions=0,
                    patch="@@ -0,0 +1,2 @@\n+# Prevue\n+Token-efficient reviews.",
                ),
            ],
        ),
        instructions=instructions,
        budget_seconds=300,
    )
