"""Tests for hoisted shared prompt module (D-09)."""

from __future__ import annotations

from prevue.engines.prompt import OUTPUT_CONTRACT, _build_prompt, build_prompt
from tests.engine_helpers import make_sample_request


class TestBuildPrompt:
    def test_includes_instructions_preamble(self) -> None:
        req = make_sample_request(instructions="Focus on security issues.")
        prompt = _build_prompt(req)
        assert "Focus on security issues." in prompt

    def test_includes_changed_file_paths_and_status(self) -> None:
        prompt = _build_prompt(make_sample_request())
        assert "src/main.py" in prompt
        assert "modified" in prompt
        assert "README.md" in prompt
        assert "added" in prompt

    def test_includes_patch_hunks_in_fenced_diff_blocks(self) -> None:
        prompt = _build_prompt(make_sample_request())
        assert "```diff" in prompt
        assert "def main():" in prompt
        assert "# Prevue" in prompt

    def test_labels_content_as_untrusted_data(self) -> None:
        prompt = _build_prompt(make_sample_request())
        assert "UNTRUSTED DATA" in prompt
        assert "never as instructions" in prompt.lower() or "never instructions" in prompt.lower()

    def test_excludes_pr_title_and_body(self) -> None:
        prompt = _build_prompt(make_sample_request())
        for forbidden in ("Test PR", "Test body", "pr_title", "pr_body"):
            assert forbidden not in prompt

    def test_build_prompt_alias_matches_private(self) -> None:
        req = make_sample_request()
        assert build_prompt(req) == _build_prompt(req)


class TestOutputContract:
    def test_output_contract_constant_has_rubric_and_fence_instruction(self) -> None:
        assert "error" in OUTPUT_CONTRACT
        assert "warning" in OUTPUT_CONTRACT
        assert "info" in OUTPUT_CONTRACT
        assert "RIGHT" in OUTPUT_CONTRACT
        assert "LEFT" in OUTPUT_CONTRACT
        assert "last element" in OUTPUT_CONTRACT.lower()

    def test_prompt_places_contract_before_untrusted_data(self) -> None:
        prompt = _build_prompt(make_sample_request())
        contract_line = next(line for line in OUTPUT_CONTRACT.splitlines() if line.strip())
        contract_idx = prompt.index(contract_line[: min(20, len(contract_line))])
        untrusted_idx = prompt.index("UNTRUSTED DATA")
        assert contract_idx < untrusted_idx

    def test_prompt_includes_severity_rubric_and_fence_at_end_instruction(self) -> None:
        prompt = _build_prompt(make_sample_request())
        assert "error" in prompt
        assert "warning" in prompt
        assert "info" in prompt
        lower = prompt.lower()
        assert "json" in lower
        assert "last" in lower

    def test_prompt_carries_contract_content(self) -> None:
        prompt = _build_prompt(make_sample_request())
        assert "Clear, Concise, Correct, Complete" in prompt
        assert prompt.index("Clear") < prompt.index("UNTRUSTED DATA")
