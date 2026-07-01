"""Contract tests for per-file LLM classification fallback (CLSF-02) and
llm_select_skills skill-name escalation fallback (D-02, Plan 09-02)."""

from __future__ import annotations

try:
    from prevue.classify.llm_fallback import llm_select_skills
except ImportError as _import_err:
    _MISSING_SELECT = _import_err
    llm_select_skills = None  # type: ignore[assignment]
else:
    _MISSING_SELECT = None

import pytest

from prevue.classify.llm_fallback import CLASSIFY_BATCH_SIZE, llm_classify
from prevue.classify.models import CANONICAL_LABEL_ORDER, GENERAL_LABEL
from prevue.engines.base import EngineAdapter
from prevue.engines.errors import EngineFailure
from prevue.models import ChangedFile, ReviewRequest, ReviewResult


def _require_llm_select_skills() -> None:
    if _MISSING_SELECT is not None:
        msg = f"llm_select_skills not yet implemented (Plan 09-02): {_MISSING_SELECT}"
        pytest.fail(msg)


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
    labels, disclosure, tokens = llm_classify([], adapter)
    assert labels == {}
    assert disclosure is None
    assert tokens is None
    assert adapter.calls == []


def test_unmatched_only() -> None:
    adapter = RecordingAdapter()
    unmatched = ["README.txt", "notes.org"]
    labels, disclosure, tokens = llm_classify(unmatched, adapter, model="cheap-model")
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

    labels, disclosure, tokens = llm_classify(["mystery.bin"], FailingAdapter())
    assert disclosure is not None
    assert labels == {GENERAL_LABEL: "(llm fallback failed)"}
    assert tokens is None


def test_batches_many_unmatched_paths() -> None:
    adapter = RecordingAdapter()
    unmatched = [f"file-{i}.txt" for i in range(CLASSIFY_BATCH_SIZE + 25)]

    labels, disclosure, tokens = llm_classify(unmatched, adapter, batch_size=CLASSIFY_BATCH_SIZE)

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

    labels, disclosure, tokens = llm_classify(unmatched, adapter, batch_size=3)

    assert adapter.calls == 2
    assert labels["ok-0.txt"] == "backend"
    assert labels["ok-1.txt"] == "backend"
    assert labels["ok-2.txt"] == "backend"
    assert labels[GENERAL_LABEL] == "(llm fallback partial)"
    assert disclosure is not None
    assert "fail-0.txt" in disclosure


# ---------------------------------------------------------------------------
# llm_select_skills tests (RED scaffold — Plan 09-02 GREEN implements these)
# ---------------------------------------------------------------------------


def _make_skill_for_select(
    *,
    name: str,
    description: str,
    bundle: str = "backend",
    body: str = "SKILL BODY CONTENT THAT MUST NOT APPEAR IN PROMPT",
):
    from prevue.skills.models import Skill

    skill = Skill(name=name, description=description, applies_to=["**/*.py"])
    skill.bundle = bundle
    skill.filename = "skill.md"
    skill.body = body
    return skill


class TestLlmSelectSkills:
    def test_returns_set_of_skill_names(self) -> None:
        """llm_select_skills returns a set of skill name strings."""
        _require_llm_select_skills()

        class SelectingAdapter(EngineAdapter):
            name = "selecting"

            def review(self, req: ReviewRequest) -> ReviewResult:
                raise NotImplementedError

            def classify_skills(
                self,
                skills: list,
                allowed_labels: tuple[str, ...] | list[str],
                *,
                model: str | None = None,
                paths: list[str] | None = None,
                diff_excerpt: str | None = None,
            ) -> dict[str, str]:
                # Returns skill names as a name→"relevant" mapping
                return {s.name: "relevant" for s in skills}

        skill = _make_skill_for_select(name="Auth Guard", description="Check auth guards.")
        result = llm_select_skills([skill], SelectingAdapter(), model=None)
        assert isinstance(result, set), "llm_select_skills must return a set"
        for item in result:
            assert isinstance(item, str), f"Expected str, got {type(item)}"

    def test_prompt_excludes_skill_body_includes_description(self) -> None:
        """Escalation prompt must include name+description but NOT the body (CR-02, T-09-05)."""
        _require_llm_select_skills()

        from prevue.engines.prompt import build_skill_select_prompt

        SENTINEL = "GAP-DEMO-SKILL-BODY-SENTINEL-MUST-NOT-APPEAR"
        DESC_TOKEN = "DESCRIPTION-TOKEN-MUST-APPEAR"
        captured_prompts: list[str] = []

        class CapturingAdapter(EngineAdapter):
            name = "capturing"

            def review(self, req: ReviewRequest) -> ReviewResult:
                raise NotImplementedError

            def classify_skills(
                self,
                skills: list,
                allowed_labels: tuple[str, ...] | list[str],
                *,
                model: str | None = None,
                paths: list[str] | None = None,
                diff_excerpt: str | None = None,
            ) -> dict[str, str]:
                # Build the real prompt the engine would receive and capture it.
                captured_prompts.append(build_skill_select_prompt(skills, allowed_labels))
                return {}

        skill = _make_skill_for_select(
            name="Auth Guard",
            description=f"Check auth guards. {DESC_TOKEN}",
            body=SENTINEL,
        )
        llm_select_skills([skill], CapturingAdapter(), model=None)
        full_prompt = "\n".join(captured_prompts)
        assert SENTINEL not in full_prompt, (
            "Skill body must never appear in the escalation prompt (progressive disclosure T-09-05)"
        )
        assert DESC_TOKEN in full_prompt, (
            "Skill description must reach the engine (CR-02 — name-only escalation is a regression)"
        )

    def test_degrade_on_not_implemented_error(self) -> None:
        """NotImplementedError from adapter degrades to None (caller may fall back)."""
        _require_llm_select_skills()

        class NotImplAdapter(EngineAdapter):
            name = "not-impl"

            def review(self, req: ReviewRequest) -> ReviewResult:
                raise NotImplementedError

            def classify_skills(
                self,
                skills: list,
                allowed_labels: tuple[str, ...] | list[str],
                *,
                model: str | None = None,
                paths: list[str] | None = None,
                diff_excerpt: str | None = None,
            ) -> dict[str, str]:
                raise NotImplementedError("no skill classify")

        skill = _make_skill_for_select(name="Auth Guard", description="Check auth guards.")
        result = llm_select_skills([skill], NotImplAdapter(), model=None)
        assert result is None, "NotImplementedError must degrade to None"

    def test_degrade_on_engine_failure(self) -> None:
        """EngineFailure degrades to None (caller may fall back)."""
        _require_llm_select_skills()

        class FailingAdapter(EngineAdapter):
            name = "failing"

            def review(self, req: ReviewRequest) -> ReviewResult:
                raise NotImplementedError

            def classify_skills(
                self,
                skills: list,
                allowed_labels: tuple[str, ...] | list[str],
                *,
                model: str | None = None,
                paths: list[str] | None = None,
                diff_excerpt: str | None = None,
            ) -> dict[str, str]:
                raise EngineFailure("engine failed")

        skill = _make_skill_for_select(name="Auth Guard", description="Check auth guards.")
        result = llm_select_skills([skill], FailingAdapter(), model=None)
        assert result is None, "EngineFailure must degrade to None"

    def test_empty_skills_returns_empty_set(self) -> None:
        """llm_select_skills with no candidate skills returns empty set."""
        _require_llm_select_skills()

        class NoopAdapter(EngineAdapter):
            name = "noop"

            def review(self, req: ReviewRequest) -> ReviewResult:
                raise NotImplementedError

            def classify(
                self,
                paths: list[str],
                allowed_labels: tuple[str, ...] | list[str],
                *,
                model: str | None = None,
            ) -> dict[str, str]:
                return {}

        result = llm_select_skills([], NoopAdapter(), model=None)
        assert result == set(), "Empty skill list must return empty set"
