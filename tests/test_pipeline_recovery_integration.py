import json

import job_state
import resumable_dispatch


class _Result:
    def __init__(self, returncode):
        self.returncode = returncode


def _authorize(monkeypatch):
    monkeypatch.setenv("SCAN_AUTHORIZATION_REF", "auth:test")
    monkeypatch.setenv("SCAN_SCOPE_REF", "scope:test")


def test_failed_shard_is_retryable_and_success_completes_job(monkeypatch, tmp_path):
    _authorize(monkeypatch)
    state_path = str(tmp_path / "state.json")
    results = iter([_Result(2), _Result(0)])
    monkeypatch.setattr(resumable_dispatch.subprocess, "run", lambda *args, **kwargs: next(results))

    assert resumable_dispatch.run_shard("recover-1", 0, 1, state_path=state_path) == 2
    failed = job_state.load_state(state_path)["jobs"]["recover-1"]
    assert failed["status"] == "running"
    assert failed["completed_shards"] == []

    assert resumable_dispatch.run_shard("recover-1", 0, 1, state_path=state_path) == 0
    completed = job_state.load_state(state_path)["jobs"]["recover-1"]
    assert completed["status"] == "completed"
    assert completed["completed_shards"] == ["shard:0"]


def test_job_waits_for_all_shards_and_retry_is_idempotent(monkeypatch, tmp_path):
    _authorize(monkeypatch)
    state_path = str(tmp_path / "state.json")
    calls = []
    monkeypatch.setattr(
        resumable_dispatch.subprocess,
        "run",
        lambda *args, **kwargs: (calls.append(args[0]) or _Result(0)),
    )

    assert resumable_dispatch.run_shard("multi-1", 0, 2, state_path=state_path) == 0
    first = job_state.load_state(state_path)["jobs"]["multi-1"]
    assert first["status"] == "running"
    assert first["completed_shards"] == ["shard:0"]

    assert resumable_dispatch.run_shard("multi-1", 1, 2, state_path=state_path) == 0
    second = job_state.load_state(state_path)["jobs"]["multi-1"]
    assert second["status"] == "completed"
    assert sorted(second["completed_shards"]) == ["shard:0", "shard:1"]

    before = len(calls)
    assert resumable_dispatch.run_shard("multi-1", 1, 2, state_path=state_path) == 0
    assert len(calls) == before
