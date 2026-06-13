"""Gemini CLI adapter skeleton — registered extension point (D-02)."""

from __future__ import annotations

from prevue.engines.base import EngineAdapter
from prevue.models import ReviewRequest, ReviewResult


class GeminiAdapter(EngineAdapter):
    """Skeleton adapter for future Gemini CLI integration.

    Intended invocation: ``gemini -p "<prompt>" --output-format json``
    Model via ``-m <model>`` (e.g. gemini-2.5-flash).
    Auth via ``GEMINI_API_KEY``.

    Functional implementation deferred — see CONTEXT D-02.
    """

    name = "gemini-cli"

    def review(self, req: ReviewRequest) -> ReviewResult:
        raise NotImplementedError("Gemini adapter planned — see ENGN-04")
