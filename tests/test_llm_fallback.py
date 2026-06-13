"""RED contract tests for per-file LLM classification fallback (CLSF-02)."""

from __future__ import annotations

from prevue.classify.llm_fallback import CLASSIFY_BATCH_SIZE, llm_classify
from prevue.classify.models import CANONICAL_LABEL_ORDER, GENERAL_LABEL
from prevue.engines.base import EngineAdapter
from prevue.engines.errors import EngineFailure
from prevue.models import ChangedFile, ReviewRequest, ReviewResult


class RecordingAdapter(EngineAdapter):
    name = "recording"

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], tuple[str, ...]]] = []

    def review(self, req: ReviewRequest) -> ReviewResult:
        raise NotImplementedError("review not used in llm_classify tests")

    def classify(
        self,
        paths: list[str],
        allowed_labels: tuple[str, ...] | list[str],
        *,
        model: str | None = None,
    ) -> dict[str, str]:
        self.calls.append((list(paths), tuple(allowed_labels)))
        return {path: "backend" for path in paths}


def _file(path: str) -> ChangedFile:
    return ChangedFile(path=path, status="modified", additions=1, deletions=0, patch="@@")


def test_no_call_when_all_matched() -> None:
    adapter = RecordingAdapter()
    labels, disclosure = llm_classify([], adapter)
    assert labels == {}
    assert disclosure is None
    assert adapter.calls == []


def test_unmatched_only() -> None:
    adapter = RecordingAdapter()
    unmatched = ["README.txt", "notes.org"]
    labels, disclosure = llm_classify(unmatched, adapter, model="cheap-model")
    assert disclosure is None
    assert set(labels.keys()) == set(unmatched)
    assert len(adapter.calls) == 1
    paths, allowed = adapter.calls[0]
    assert paths == unmatched
    assert tuple(allowed) == CANONICAL_LABEL_ORDER


def test_degrade_to_general() -> None:
    class FailingAdapter(EngineAdapter):
        name = "failing"

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise NotImplementedError("review not used")

        def classify(
            self,
            paths: list[str],
            allowed_labels: tuple[str, ...] | list[str],
            *,
            model: str | None = None,
        ) -> dict[str, str]:
            raise NotImplementedError("no classify")

    labels, disclosure = llm_classify(["mystery.bin"], FailingAdapter())
    assert disclosure is not None
    assert labels == {GENERAL_LABEL: "(llm fallback failed)"}


def test_batches_many_unmatched_paths() -> None:
    adapter = RecordingAdapter()
    unmatched = [f"file-{i}.txt" for i in range(CLASSIFY_BATCH_SIZE + 25)]

    labels, disclosure = llm_classify(unmatched, adapter, batch_size=CLASSIFY_BATCH_SIZE)

    assert disclosure is None
    assert set(labels.keys()) == set(unmatched)
    assert len(adapter.calls) == 2
    assert len(adapter.calls[0][0]) == CLASSIFY_BATCH_SIZE
    assert len(adapter.calls[1][0]) == 25


def test_batch_failure_degrades_remaining_paths() -> None:
    class PartialFailAdapter(EngineAdapter):
        name = "partial-fail"

        def __init__(self) -> None:
            self.calls = 0

        def review(self, req: ReviewRequest) -> ReviewResult:
            raise NotImplementedError("review not used")

        def classify(
            self,
            paths: list[str],
            allowed_labels: tuple[str, ...] | list[str],
            *,
            model: str | None = None,
        ) -> dict[str, str]:
            self.calls += 1
            if self.calls == 1:
                return {path: "backend" for path in paths}
            raise EngineFailure("batch 2 failed")

    adapter = PartialFailAdapter()
    unmatched = [f"ok-{i}.txt" for i in range(3)] + [f"fail-{i}.txt" for i in range(3)]

    labels, disclosure = llm_classify(unmatched, adapter, batch_size=3)

    assert adapter.calls == 2
    assert labels["ok-0.txt"] == "backend"
    assert labels["ok-1.txt"] == "backend"
    assert labels["ok-2.txt"] == "backend"
    assert labels[GENERAL_LABEL] == "(llm fallback partial)"
    assert disclosure is not None
    assert "fail-0.txt" in disclosure
