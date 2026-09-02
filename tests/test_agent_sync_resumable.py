import json

import agent_sync


def test_agent_sync_job_adapter_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_sync, "JOB_STATE_FILE", str(tmp_path / "job_state.json"))

    first = agent_sync.start_resumable_job(
        "job-42", authorization_ref="auth-42", scope_ref="scope-7"
    )
    second = agent_sync.start_resumable_job(
        "job-42", authorization_ref="auth-42", scope_ref="scope-7"
    )
    assert first["job_id"] == second["job_id"] == "job-42"
    assert second["status"] == "running"

    agent_sync.record_job_step("job-42", "shard-0001")
    agent_sync.record_job_step("job-42", "shard-0001")
    assert agent_sync.job_step_completed("job-42", "shard-0001")

    completed = agent_sync.finish_resumable_job("job-42")
    assert completed["status"] == "completed"


def test_agent_sync_adapter_rejects_unbounded_or_missing_refs(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_sync, "JOB_STATE_FILE", str(tmp_path / "job_state.json"))

    try:
        agent_sync.start_resumable_job("job-1", authorization_ref="", scope_ref="scope")
    except PermissionError:
        pass
    else:
        raise AssertionError("missing authorization must fail closed")

    try:
        agent_sync.start_resumable_job("job-1", authorization_ref="auth", scope_ref="bad ref")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid scope reference must be rejected")


def test_job_state_adapter_does_not_persist_secret_material(tmp_path, monkeypatch):
    path = tmp_path / "job_state.json"
    monkeypatch.setattr(agent_sync, "JOB_STATE_FILE", str(path))
    agent_sync.start_resumable_job("job-safe", authorization_ref="auth-ref", scope_ref="scope-ref")
    agent_sync.record_job_step("job-safe", "shard-1")
    raw = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(raw).lower()
    assert "password" not in text
    assert "secret" not in text
    assert "username" not in text
    assert "192.0.2.10" not in text
