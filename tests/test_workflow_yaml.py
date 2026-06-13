"""Static SECR-01 guards for .github/workflows/review.yml."""

from __future__ import annotations

from pathlib import Path

import yaml

REVIEW_WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "review.yml"
REUSABLE_WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "prevue-review.yml"
)

SETUP_UV_SHA = "fac544c07dec837d0ccb6301d7b5580bf5edae39"
CHECKOUT_SHA = "df4cb1c069e1874edd31b4311f1884172cec0e10"
COPILOT_CLI_VERSION = "1.0.61"
CLAUDE_CODE_CLI_VERSION = "2.1.177"


def _load_review_workflow() -> dict:
    with REVIEW_WORKFLOW.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_reusable_workflow() -> dict:
    with REUSABLE_WORKFLOW.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_review_workflow_exists() -> None:
    assert REVIEW_WORKFLOW.is_file()


def test_pull_request_trigger_only() -> None:
    wf = _load_review_workflow()
    on = wf.get("on") or wf.get(True)  # yaml key `on` may parse as True
    assert on is not None
    if isinstance(on, dict):
        assert "pull_request" in on
        assert "pull_request_target" not in on
    else:
        assert on == "pull_request"


def test_pull_request_types() -> None:
    wf = _load_review_workflow()
    on = wf.get("on") or wf.get(True)
    assert isinstance(on, dict)
    pr = on["pull_request"]
    if isinstance(pr, dict):
        assert pr.get("branches") == ["main"]
        assert pr.get("types") == ["opened", "synchronize", "reopened", "ready_for_review"]


def test_minimal_permissions() -> None:
    wf = _load_review_workflow()
    assert wf["permissions"] == {
        "contents": "read",
        "pull-requests": "write",
        "checks": "write",
    }


def test_no_pull_request_target_in_source() -> None:
    text = REVIEW_WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target" not in text


def test_review_yml_uses_reusable_workflow() -> None:
    wf = _load_review_workflow()
    review_job = wf.get("jobs", {}).get("review", {})
    assert review_job.get("if") == (
        "${{ github.event.pull_request.head.repo.full_name == github.repository }}"
    )
    uses = review_job.get("uses", "")
    assert "./.github/workflows/prevue-review.yml" in uses or uses.endswith("prevue-review.yml")
    assert "runs-on" not in review_job
    assert "steps" not in review_job


def test_review_yml_named_secrets_no_inherit() -> None:
    text = REVIEW_WORKFLOW.read_text(encoding="utf-8")
    assert "secrets: inherit" not in text
    assert "secrets:inherit" not in text.replace(" ", "")
    wf = _load_review_workflow()
    secrets = wf.get("jobs", {}).get("review", {}).get("secrets", {})
    assert "copilot-github-token" in secrets
    assert "${{ secrets.COPILOT_GITHUB_TOKEN }}" in str(secrets["copilot-github-token"])


def test_prevue_engine_from_repo_variable_in_caller() -> None:
    text = REVIEW_WORKFLOW.read_text(encoding="utf-8")
    assert "vars.PREVUE_ENGINE" in text


def test_dogfood_caller_passes_prevue_ref_head_sha() -> None:
    wf = _load_review_workflow()
    with_block = wf.get("jobs", {}).get("review", {}).get("with", {})
    assert with_block.get("prevue-ref") == "${{ github.event.pull_request.head.sha }}"


def test_single_prevue_review_invocation_in_reusable() -> None:
    wf = _load_reusable_workflow()
    invocations: list[str] = []
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            run = step.get("run", "")
            if "prevue review" in run:
                invocations.append(run.strip())
    assert len(invocations) == 1
    assert invocations[0] == "uv run prevue review"


def test_copilot_token_env_separate_from_github_token_in_reusable() -> None:
    wf = _load_reusable_workflow()
    review_step = None
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            if step.get("run", "").strip() == "uv run prevue review":
                review_step = step
    assert review_step is not None
    review_env = review_step.get("env") or {}
    assert "GITHUB_TOKEN" in review_env
    assert "${{ github.token }}" in str(review_env["GITHUB_TOKEN"])
    assert review_env["COPILOT_GITHUB_TOKEN"] == (
        "${{ inputs.engine == 'copilot-cli' && secrets.copilot-github-token || '' }}"
    )
    assert review_env["ANTHROPIC_API_KEY"] == (
        "${{ inputs.engine == 'claude-code-cli' && secrets.anthropic-api-key || '' }}"
    )
    assert review_env["CURSOR_API_KEY"] == (
        "${{ inputs.engine == 'cursor-cli' && secrets.cursor-api-key || '' }}"
    )
    assert review_env["PREVUE_CONSUMER_ROOT"] == "${{ github.workspace }}/consumer"
    assert review_env["PREVUE_CONFIG_PATH"] == "${{ inputs.config-path }}"


def test_checkout_is_sha_pinned_in_reusable() -> None:
    wf = _load_reusable_workflow()
    checkout_uses: list[str] = []
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if "checkout" in uses:
                checkout_uses.append(uses)
    assert checkout_uses
    assert all(u == f"actions/checkout@{CHECKOUT_SHA}" for u in checkout_uses)


def test_setup_uv_is_sha_pinned_in_reusable() -> None:
    wf = _load_reusable_workflow()
    setup_uv_uses = None
    uv_version = None
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if uses.startswith("astral-sh/setup-uv@"):
                setup_uv_uses = uses
                uv_version = (step.get("with") or {}).get("version")
    assert setup_uv_uses == f"astral-sh/setup-uv@{SETUP_UV_SHA}"
    assert uv_version == "0.11.21"


def test_copilot_cli_version_pinned_in_reusable() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert f"npm install -g @github/copilot@{COPILOT_CLI_VERSION}" in text
    assert "copilot-cli)" in text


def test_claude_install_uses_pinned_npm_package_in_reusable() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert f"npm install -g @anthropic-ai/claude-code@{CLAUDE_CODE_CLI_VERSION}" in text
    assert "claude.ai/install.sh" not in text


def test_cursor_install_uses_official_curl_installer_in_reusable() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "cursor.com/install" in text
    assert "npm install -g cursor-agent" not in text
    assert "cursor.com/docs/cli" in text
    assert "impostor" in text


def test_engine_secrets_passed_directly_to_review_step_in_reusable() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "Prepare engine credentials" not in text
    assert "GITHUB_ENV" not in text
    wf = _load_reusable_workflow()
    review_step = None
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            if step.get("run", "").strip() == "uv run prevue review":
                review_step = step
                break
    assert review_step is not None
    env = review_step.get("env") or {}
    assert "inputs.engine ==" in str(env["ANTHROPIC_API_KEY"])
    assert "inputs.engine ==" in str(env["CURSOR_API_KEY"])


def test_install_engine_cli_before_run_review_in_reusable() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "Install engine CLI" in text
    assert "copilot-cli)" in text
    idx_install = text.index("Install engine CLI")
    idx_run = text.index("uv run prevue review")
    assert idx_install < idx_run


def test_consumer_checkout_uses_base_sha_in_reusable() -> None:
    wf = _load_reusable_workflow()
    consumer_refs: list[str] = []
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if "checkout" not in uses:
                continue
            with_block = step.get("with") or {}
            path = str(with_block.get("path", ""))
            if path == "consumer":
                consumer_refs.append(str(with_block.get("ref", "")))
    assert consumer_refs == ["${{ github.event.pull_request.base.sha }}"]
