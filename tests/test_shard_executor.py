import subprocess

import pytest

import shard_executor


def _env(monkeypatch):
    monkeypatch.setenv("SCAN_JOB_ID", "job-42")
    monkeypatch.setenv("SCAN_AUTHORIZATION_REF", "auth-42")
    monkeypatch.setenv("SCAN_SCOPE_REF", "scope-42")


def test_shard_requires_authorization(monkeypatch, tmp_path):
    monkeypatch.delenv("SCAN_AUTHORIZATION_REF", raising=False)
    monkeypatch.setenv("SCAN_JOB_ID", "job-42")
    monkeypatch.setenv("SCAN_SCOPE_REF", "scope-42")
    with pytest.raises(PermissionError):
        shard_executor.execute_shard("0/4", "true", state_path=tmp_path / "state.json")


def test_completed_shard_is_not_reexecuted(monkeypatch, tmp_path):
    _env(monkeypatch)
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    path = tmp_path / "state.json"
    assert shard_executor.execute_shard("0/4", "echo shard", state_path=path) == 0
    assert shard_executor.execute_shard("0/4", "echo shard", state_path=path) == 0
    assert calls == ["echo shard"]


def test_failed_shard_remains_resumable(monkeypatch, tmp_path):
    _env(monkeypatch)
    path = tmp_path / "state.json"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 9),
    )
    assert shard_executor.execute_shard("1/4", "false", state_path=path) == 9
    from job_state import shard_completed
    assert not shard_completed("job-42", "1/4", state_path=path)
