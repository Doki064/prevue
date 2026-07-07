"""Static SECR-01 guards for .github/workflows/review.yml."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

REVIEW_WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "review.yml"
REUSABLE_WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "prevue-review.yml"
)
COMMAND_WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "prevue-command.yml"
)
COMMAND_RUN_WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "prevue-command-run.yml"
)
INSTALL_SCRIPT = (
    Path(__file__).resolve().parents[1] / ".github" / "scripts" / "install-engine-cli.sh"
)

SETUP_UV_SHA = "fac544c07dec837d0ccb6301d7b5580bf5edae39"
CHECKOUT_SHA = "df4cb1c069e1874edd31b4311f1884172cec0e10"
COPILOT_CLI_VERSION = "1.0.67"
CLAUDE_CODE_CLI_VERSION = "2.1.177"


def _load_review_workflow() -> dict:
    with REVIEW_WORKFLOW.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_reusable_workflow() -> dict:
    with REUSABLE_WORKFLOW.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_review_workflow_exists() -> None:
    assert REVIEW_WORKFLOW.is_file()


def test_ci_local_script_exists_and_is_executable() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "ci-local.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK)


def test_dogfood_concurrency_cancels_superseded_runs_per_pr() -> None:
    concurrency = _load_review_workflow().get("concurrency", {})
    assert concurrency.get("group") == "prevue-${{ github.event.pull_request.number }}"
    assert concurrency.get("cancel-in-progress") is True


def test_dogfood_triggers_on_pull_request_and_waits_for_ci() -> None:
    wf = _load_review_workflow()
    on = wf.get("on") or wf.get(True)
    assert isinstance(on, dict)
    pr_on = on.get("pull_request", {})
    assert pr_on.get("branches") == ["main"]
    for event_type in ("opened", "synchronize", "reopened", "ready_for_review"):
        assert event_type in pr_on.get("types", [])

    jobs = wf.get("jobs", {})
    assert "wait-ci" in jobs
    wait_run = jobs["wait-ci"]["steps"][0]["run"]
    assert "--workflow ci.yml" in wait_run
    assert "--event pull_request" in wait_run
    assert jobs["wait-ci"]["outputs"]["ci_ok"] == "${{ steps.wait.outputs.ci_ok }}"

    review_job = jobs.get("review", {})
    assert review_job.get("needs") == "wait-ci"
    wait_if = jobs["wait-ci"].get("if", "")
    review_if = review_job.get("if", "")
    assert "pull_request.head.repo.full_name == github.repository" in wait_if
    assert "pull_request.head.repo.full_name == github.repository" in review_if
    assert "needs.wait-ci.outputs.ci_ok == 'true'" in review_if
    assert "pull_request.draft != true" in review_if


def test_wait_ci_maps_terminal_conclusions_without_poll_loop() -> None:
    wait_run = _load_review_workflow()["jobs"]["wait-ci"]["steps"][0]["run"]
    assert "skipped|neutral" in wait_run
    assert "Unknown CI conclusion" in wait_run
    assert "*) sleep 15" not in wait_run
    assert wait_run.count("ci_ok=false") >= 2


def test_wait_ci_polls_pr_head_sha_for_ci_run() -> None:
    wf = _load_review_workflow()
    wait_env = wf["jobs"]["wait-ci"]["steps"][0]["env"]
    assert wait_env.get("CI_POLL_SHA") == "${{ github.event.pull_request.head.sha }}"
    assert wait_env.get("CI_BRANCH") == "${{ github.head_ref }}"
    assert "${{ github.sha }}" not in str(wait_env)
    with_block = wf["jobs"]["review"]["with"]
    assert with_block.get("pr-head-sha") == "${{ github.event.pull_request.head.sha }}"


def test_wait_ci_retries_gh_and_exits_when_workflow_missing() -> None:
    wait_run = _load_review_workflow()["jobs"]["wait-ci"]["steps"][0]["run"]
    assert "gh workflow view ci.yml" in wait_run
    assert "Workflow ci.yml not found" in wait_run
    assert "fetch_ci_runs()" in wait_run
    assert "gh run list failed (attempt" in wait_run
    assert "gh run list unavailable; continuing poll" in wait_run
    assert '--branch "$CI_BRANCH"' in wait_run
    assert "--limit 50" in wait_run


def test_wait_ci_selects_latest_run_and_skips_on_timeout() -> None:
    wait_run = _load_review_workflow()["jobs"]["wait-ci"]["steps"][0]["run"]
    assert "createdAt" in wait_run
    assert "sort_by(.createdAt)" in wait_run
    assert "CI_POLL_SHA" in wait_run
    assert '--commit "$CI_POLL_SHA"' in wait_run
    assert "Timed out waiting for pull_request CI" in wait_run
    timeout_tail = wait_run.split("Timed out waiting for pull_request CI", 1)[1]
    assert "ci_ok=false" in timeout_tail
    assert "exit 1" not in timeout_tail


def test_dogfood_passes_pr_shas_via_pull_request_inputs() -> None:
    wf = _load_review_workflow()
    with_block = wf.get("jobs", {}).get("review", {}).get("with", {})
    assert with_block.get("prevue-ref") == "${{ github.event.pull_request.head.sha }}"
    assert with_block.get("pr-head-sha") == "${{ github.event.pull_request.head.sha }}"
    assert with_block.get("consumer-base-sha") == "${{ github.event.pull_request.base.sha }}"


def test_minimal_permissions() -> None:
    """WKFL-04: review job grants contents:write for LIFE-04 resolveReviewThread."""
    wf = _load_review_workflow()
    assert "permissions" not in wf
    review_perms = wf.get("jobs", {}).get("review", {}).get("permissions", {})
    assert review_perms == {
        "contents": "write",
        "pull-requests": "write",
        "checks": "write",
    }
    wait_perms = wf.get("jobs", {}).get("wait-ci", {}).get("permissions", {})
    assert wait_perms == {"actions": "read"}


def test_no_pull_request_target_in_source() -> None:
    text = REVIEW_WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target" not in text


def test_review_yml_uses_reusable_workflow() -> None:
    wf = _load_review_workflow()
    review_job = wf.get("jobs", {}).get("review", {})
    assert review_job.get("needs") == "wait-ci"
    assert "needs.wait-ci.outputs.ci_ok == 'true'" in review_job.get("if", "")
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
    reusable = _load_reusable_workflow()
    on = reusable.get("on") or reusable.get(True) or {}
    workflow_call_secrets = on["workflow_call"]["secrets"]
    for name in workflow_call_secrets:
        assert name in secrets, f"missing workflow_call secret {name!r} on review job"
    assert "${{ secrets.COPILOT_GITHUB_TOKEN }}" in str(secrets["copilot-github-token"])
    assert "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}" in str(secrets["claude-code-oauth-token"])
    assert "${{ secrets.CURSOR_API_KEY }}" in str(secrets["cursor-api-key"])


def test_dogfood_caller_engine_from_repo_variable() -> None:
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
    assert review_env["CLAUDE_CODE_OAUTH_TOKEN"] == (
        "${{ inputs.engine == 'claude-code-cli' && secrets.claude-code-oauth-token || '' }}"
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
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert f"npm install -g @github/copilot@{COPILOT_CLI_VERSION}" in script
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "install-engine-cli.sh" in text


def test_claude_install_uses_pinned_npm_package_in_reusable() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert f"npm install -g @anthropic-ai/claude-code@{CLAUDE_CODE_CLI_VERSION}" in script
    assert "claude.ai/install.sh" not in script


def test_cursor_install_uses_official_curl_installer_in_reusable() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "cursor.com/install" in script
    assert "npm install -g cursor-agent" not in script
    assert "PREVUE_CURSOR_INSTALL_SHA256" in script


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
    assert "inputs.engine ==" in str(env["CLAUDE_CODE_OAUTH_TOKEN"])
    assert "inputs.engine ==" in str(env["CURSOR_API_KEY"])


def test_install_engine_cli_before_run_review_in_reusable() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "Install engine CLI" in text
    assert "install-engine-cli.sh" in text
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
    assert len(consumer_refs) == 1
    ref = consumer_refs[0]
    assert "inputs.consumer-base-sha" in ref
    assert "github.event.pull_request.base.sha" in ref


def _get_reusable_steps() -> list[dict]:
    """Return the ordered list of steps from the reusable workflow's review job."""
    wf = _load_reusable_workflow()
    for job in wf.get("jobs", {}).values():
        steps = job.get("steps", [])
        if steps:
            return steps
    return []


def test_preflight_noop_step_precedes_engine_install_in_reusable() -> None:
    """A step with id 'preflight' exists and appears before 'Install engine CLI'."""
    steps = _get_reusable_steps()
    step_ids = [s.get("id", "") for s in steps]
    step_names = [s.get("name", "") for s in steps]

    assert "preflight" in step_ids, "No step with id='preflight' found in reusable workflow"

    preflight_idx = step_ids.index("preflight")
    install_idx = next(
        (i for i, n in enumerate(step_names) if "Install engine CLI" in n),
        None,
    )
    assert install_idx is not None, "'Install engine CLI' step not found"
    assert preflight_idx < install_idx, (
        f"preflight (idx={preflight_idx}) must precede Install engine CLI (idx={install_idx})"
    )


def test_engine_install_gated_on_preflight_noop_in_reusable() -> None:
    """Install engine CLI step gates on steps.preflight.outputs.noop."""
    steps = _get_reusable_steps()
    install_step = next(
        (s for s in steps if "Install engine CLI" in s.get("name", "")),
        None,
    )
    assert install_step is not None, "'Install engine CLI' step not found"
    if_expr = install_step.get("if", "")
    assert "steps.preflight.outputs.noop" in str(if_expr), (
        f"'Install engine CLI' step must gate on steps.preflight.outputs.noop; got: {if_expr!r}"
    )


def test_preflight_delegates_sticky_lookup_to_python() -> None:
    """Preflight sticky resolution uses prevue preflight (trusted-owner parity)."""
    steps = _get_reusable_steps()
    preflight = next(s for s in steps if s.get("id") == "preflight")
    run_script = preflight.get("run", "")
    env = preflight.get("env") or {}
    assert "uv run prevue preflight" in run_script
    assert "repos/$REPO/issues/$PR_NUMBER/comments" not in run_script
    assert env.get("PREVUE_STICKY_OWNER_LOGINS") == "${{ vars.PREVUE_STICKY_OWNER_LOGINS }}"


def test_run_review_step_exports_sticky_owner_logins() -> None:
    steps = _get_reusable_steps()
    review_step = next(s for s in steps if s.get("run", "").strip() == "uv run prevue review")
    env = review_step.get("env") or {}
    assert env.get("PREVUE_STICKY_OWNER_LOGINS") == "${{ vars.PREVUE_STICKY_OWNER_LOGINS }}"


def test_preflight_invokes_prevue_preflight_cli() -> None:
    """Preflight noop decision delegates to prevue preflight (Python parity)."""
    steps = _get_reusable_steps()
    preflight = next(s for s in steps if s.get("id") == "preflight")
    run_script = preflight.get("run", "")
    assert "uv run prevue preflight" in run_script
    assert preflight.get("working-directory") == ".prevue"


def test_reusable_workflow_no_secrets_inherit() -> None:
    """Reusable workflow must not use secrets: inherit (WKFL-04 trust boundary)."""
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert "secrets: inherit" not in text, "Reusable workflow must not use secrets: inherit"
    # contents:write may be present for documented LIFE-04 resolveReviewThread scope.
    if "contents: write" in text:
        assert "LIFE-04" in text or "resolveReviewThread" in text


def test_command_workflow_early_write_permission_check() -> None:
    """Read-only COLLABORATOR passes association filter but must fail before checkout."""
    text = COMMAND_WORKFLOW.read_text(encoding="utf-8")
    assert "Write access check" in text
    assert "collaborators/" in text and "permission" in text
    assert "write access" in text.lower()
    assert "steps.write_check.outputs.allowed == 'true'" in text


def test_install_engine_cli_uses_shared_script() -> None:
    text = REUSABLE_WORKFLOW.read_text(encoding="utf-8")
    assert ".github/scripts/install-engine-cli.sh" in text
    assert "npm install -g @github/copilot@" in (
        Path(__file__).resolve().parents[1] / ".github/scripts/install-engine-cli.sh"
    ).read_text(encoding="utf-8")


def test_command_workflow_consumer_checkout_uses_base_sha() -> None:
    wf = yaml.safe_load(COMMAND_RUN_WORKFLOW.read_text(encoding="utf-8"))
    consumer_refs: list[str] = []
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if "checkout" not in uses:
                continue
            with_block = step.get("with") or {}
            if str(with_block.get("path", "")) == "consumer":
                consumer_refs.append(str(with_block.get("ref", "")))
    assert consumer_refs == ["${{ github.event.client_payload.base_sha }}"]


def test_command_gate_dispatches_privileged_run_after_pin() -> None:
    text = COMMAND_WORKFLOW.read_text(encoding="utf-8")
    write_idx = text.index("Write access check")
    pinned_idx = text.index("Resolve pinned refs")
    dispatch_idx = text.index("Dispatch privileged command run")
    assert write_idx < pinned_idx < dispatch_idx
    assert "repos/${REPOSITORY}/dispatches" in text
    assert "prevue-command" in text
    assert "path: .prevue" in text
    assert "path: consumer" not in text


def test_command_run_uses_repository_dispatch_only() -> None:
    text = COMMAND_RUN_WORKFLOW.read_text(encoding="utf-8")
    assert "repository_dispatch:" in text
    assert "prevue-command" in text
    assert "workflow_dispatch:" not in text


def test_command_run_concurrency_cancels_superseded_runs_per_issue() -> None:
    wf = yaml.safe_load(COMMAND_RUN_WORKFLOW.read_text(encoding="utf-8"))
    concurrency = wf.get("concurrency", {})
    expected_group = "prevue-command-${{ github.event.client_payload.issue_number }}"
    assert concurrency.get("group") == expected_group
    assert concurrency.get("cancel-in-progress") is True


def test_command_run_checkouts_trusted_prevue_ref() -> None:
    text = COMMAND_RUN_WORKFLOW.read_text(encoding="utf-8")
    framework_block = text.split("Checkout Prevue framework", 1)[1].split("Set up uv", 1)[0]
    assert "ref: ${{ vars.PREVUE_REF || 'main' }}" in framework_block
    assert "client_payload.framework_sha" not in framework_block


def test_command_workflow_exports_sticky_owner_logins() -> None:
    wf = yaml.safe_load(COMMAND_RUN_WORKFLOW.read_text(encoding="utf-8"))
    command_env = None
    for job in wf.get("jobs", {}).values():
        for step in job.get("steps", []):
            if step.get("run", "").strip() == "uv run prevue command":
                command_env = step.get("env") or {}
    assert command_env is not None
    assert command_env.get("PREVUE_STICKY_OWNER_LOGINS") == "${{ vars.PREVUE_STICKY_OWNER_LOGINS }}"


def test_command_workflow_fork_guard_and_auth_filter() -> None:
    text = COMMAND_WORKFLOW.read_text(encoding="utf-8")
    assert "Fork PR guard" in text
    assert "COLLABORATOR" in text
    assert "OWNER" in text
    assert "secrets: inherit" not in text
    assert "actions: write" in text
    run_text = COMMAND_RUN_WORKFLOW.read_text(encoding="utf-8")
    assert "contents: write" in run_text


def test_command_dispatch_passes_comment_body_via_repository_dispatch() -> None:
    """Untrusted comment body must reach dispatch payload via file, not shell -f."""
    text = COMMAND_WORKFLOW.read_text(encoding="utf-8")
    dispatch = text.split("Dispatch privileged command run", 1)[1]
    assert '--rawfile comment_body "${BODY_FILE}"' in dispatch
    assert "gh workflow run prevue-command-run.yml" not in dispatch


def test_command_run_revalidates_gate_authorization() -> None:
    text = COMMAND_RUN_WORKFLOW.read_text(encoding="utf-8")
    assert "Re-validate gate authorization" in text
    assert "uv run prevue gate-revalidate" in text
    assert "python3 - <<'PY'" not in text
    body_idx = text.index("Write dispatch comment body")
    checkout_idx = text.index("Checkout Prevue framework")
    revalidate_idx = text.index("Re-validate gate authorization")
    consumer_idx = text.index("Checkout consumer base ref")
    engine_idx = text.index("Install engine CLI")
    assert body_idx < checkout_idx
    assert checkout_idx < revalidate_idx
    assert revalidate_idx < consumer_idx
    assert revalidate_idx < engine_idx


def test_command_run_materializes_event_via_cli() -> None:
    text = COMMAND_RUN_WORKFLOW.read_text(encoding="utf-8")
    assert "uv run prevue materialize-comment-event" in text
    assert "PREVUE_COMMENT_BODY_PATH" in text
    assert "PREVUE_COMMENT_BODY:" not in text
    assert "PREVUE_COMMENT_AUTHOR_ASSOCIATION" in text


def test_command_gate_detects_needs_engine_via_python() -> None:
    text = COMMAND_WORKFLOW.read_text(encoding="utf-8")
    assert "needs_engine_for_body" in text
    assert "grep -m1 '^/prevue '" not in text
