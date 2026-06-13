"""Parametrized contract suite over registered engine adapters (D-11)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from prevue.engines.errors import AuthError
from prevue.engines.registry import ENGINES, get_adapter
from tests.engine_helpers import (
    PROSE_REVIEW,
    VALID_FINDING,
    VALID_TOKEN,
    make_sample_request,
    stdout_with_fence,
)

FUNCTIONAL = [name for name in ENGINES if name != "gemini-cli"]

AUTH_ENV: dict[str, tuple[str, str | None]] = {
    "copilot-cli": ("COPILOT_GITHUB_TOKEN", VALID_TOKEN),
    "claude-code-cli": ("ANTHROPIC_API_KEY", "sk-ant-test-key"),
    "cursor-cli": ("CURSOR_API_KEY", "cur_test_key"),
}


@pytest.fixture(params=FUNCTIONAL)
def engine_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def adapter(engine_name: str):
    return get_adapter(engine_name)


@pytest.fixture
def authed_env(engine_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in AUTH_ENV:
        env_var, _ = AUTH_ENV[name]
        monkeypatch.delenv(env_var, raising=False)
    env_var, value = AUTH_ENV[engine_name]
    if value:
        monkeypatch.setenv(env_var, value)


def test_valid_fence_returns_result(
    engine_name: str, adapter, authed_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdout = stdout_with_fence(payload=[VALID_FINDING])

    def _success(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", _success)
    result = adapter.review(make_sample_request())
    assert result.degraded is False
    assert len(result.findings) == 1
    assert result.summary_markdown == PROSE_REVIEW
    assert result.engine_meta.get("retried") is False


def test_unparseable_degrades(
    engine_name: str, adapter, authed_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=PROSE_REVIEW, stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    result = adapter.review(make_sample_request())
    assert result.degraded is True
    assert result.findings == []
    assert "parse_error" in result.engine_meta


def test_bad_then_good_sets_retried(
    engine_name: str, adapter, authed_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str | None] = []

    def _run(_cmd, input=None, **_kwargs):
        calls.append(input)
        stdout = PROSE_REVIEW if len(calls) == 1 else stdout_with_fence(payload=[VALID_FINDING])
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    result = adapter.review(make_sample_request())
    assert len(calls) == 2
    assert result.degraded is False
    assert len(result.findings) == 1
    assert result.engine_meta.get("retried") is True


def test_missing_credential_raises_auth_error(
    engine_name: str, adapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    for env_var, _ in AUTH_ENV.values():
        monkeypatch.delenv(env_var, raising=False)

    called = False

    def _run(*_args, **_kwargs):
        nonlocal called
        called = True
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    with pytest.raises(AuthError):
        adapter.review(make_sample_request())
    assert not called


def test_vendor_argv(
    engine_name: str, adapter, authed_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def _capture(cmd, input=None, **_kwargs):
        captured["cmd"] = list(cmd)
        captured["input"] = input
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    adapter.review(make_sample_request())

    cmd = captured["cmd"]
    if engine_name == "copilot-cli":
        assert cmd == ["copilot", "-s", "--no-ask-user"]
        assert captured["input"] is not None
    elif engine_name == "claude-code-cli":
        assert cmd == ["claude", "--bare", "-p", "--output-format", "text"]
        assert captured["input"] is not None
    elif engine_name == "cursor-cli":
        assert cmd[:4] == ["cursor-agent", "-p", "--output-format", "text"]
        assert "-f" in cmd
        assert "--force" not in cmd
    else:
        pytest.fail(f"Unexpected engine {engine_name!r}")


def test_claude_model_mapping_on_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    captured: dict = {}

    def _capture(cmd, input=None, **_kwargs):
        captured["cmd"] = list(cmd)
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    req = make_sample_request().model_copy(update={"model": "sonnet"})
    get_adapter("claude-code-cli").review(req)
    assert captured["cmd"] == [
        "claude",
        "--bare",
        "-p",
        "--output-format",
        "text",
        "--model",
        "sonnet",
    ]


def test_cursor_model_mapping_and_prompt_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "cur_test_key")
    captured: dict = {}

    def _capture(cmd, input=None, **_kwargs):
        captured["cmd"] = list(cmd)
        file_idx = cmd.index("-f") + 1
        with open(cmd[file_idx], encoding="utf-8") as f:
            captured["prompt"] = f.read()
        return SimpleNamespace(returncode=0, stdout=stdout_with_fence(), stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    req = make_sample_request().model_copy(update={"model": "sonnet-4"})
    get_adapter("cursor-cli").review(req)
    cmd = captured["cmd"]
    assert cmd[:4] == ["cursor-agent", "-p", "--output-format", "text"]
    assert ["-m", "sonnet-4"] == cmd[-2:]
    assert "src/main.py" in captured["prompt"]

