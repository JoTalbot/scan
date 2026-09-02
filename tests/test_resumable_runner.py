import subprocess

import pytest

import resumable_runner


def test_runner_requires_explicit_context(monkeypatch):
    monkeypatch.delenv("SCAN_AUTHORIZATION_REF", raising=False)
    monkeypatch.delenv("SCAN_SCOPE_REF", raising=False)
    monkeypatch.delenv("SCAN_JOB_ID", raising=False)
    with pytest.raises(PermissionError):
        resumable_runner.run_step("scan", "true")


def test_runner_marks_success_and_skips_completed(monkeypatch, tmp_path):
    monkeypatch.setenv("SCAN_AUTHORIZATION_REF", "auth-1")
    monkeypatch.setenv("SCAN_SCOPE_REF", "scope-1")
    monkeypatch.setenv("SCAN_JOB_ID", "job-1")
    state_path = tmp_path / "state.json"
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert resumable_runner.run_step("scan", "echo safe", state_path=state_path) == 0
    assert resumable_runner.run_step("scan", "echo safe", state_path=state_path) == 0
    assert calls == ["echo safe"]


def test_runner_does_not_mark_failed_step(monkeypatch, tmp_path):
    monkeypatch.setenv("SCAN_AUTHORIZATION_REF", "auth-1")
    monkeypatch.setenv("SCAN_SCOPE_REF", "scope-1")
    monkeypatch.setenv("SCAN_JOB_ID", "job-1")
    state_path = tmp_path / "state.json"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 7),
    )
    assert resumable_runner.run_step("scan", "false", state_path=state_path) == 7
    from job_state import step_completed
    assert not step_completed("job-1", "scan", state_path=state_path)
