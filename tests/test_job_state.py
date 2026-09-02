import json

import pytest

from job_state import complete_job, load_state, mark_step, start_job, step_completed


def test_job_state_is_resumable_and_idempotent(tmp_path):
    path = tmp_path / "job_state.json"
    first = start_job("job-1", authorization_ref="auth-1", scope_ref="scope-1", state_path=path)
    mark_step("job-1", "scan", state_path=path)
    second = start_job("job-1", authorization_ref="auth-1", scope_ref="scope-1", state_path=path)

    assert first["job_id"] == "job-1"
    assert second["status"] == "running"
    assert step_completed("job-1", "scan", state_path=path)
    assert load_state(path)["jobs"]["job-1"]["completed_steps"] == ["scan"]


def test_completed_job_is_not_reset(tmp_path):
    path = tmp_path / "job_state.json"
    start_job("job-2", authorization_ref="auth-2", scope_ref="scope-2", state_path=path)
    mark_step("job-2", "scan", state_path=path)
    completed = complete_job("job-2", state_path=path)
    resumed = start_job("job-2", authorization_ref="auth-2", scope_ref="scope-2", state_path=path)
    assert completed["status"] == "completed"
    assert resumed["status"] == "completed"
    assert resumed["completed_steps"] == ["scan"]


def test_job_state_requires_explicit_authorization(tmp_path):
    with pytest.raises(PermissionError):
        start_job("job-3", authorization_ref="", scope_ref="scope-3", state_path=tmp_path / "state.json")


def test_job_state_persists_only_operational_refs(tmp_path):
    path = tmp_path / "state.json"
    start_job("job-4", authorization_ref="auth-ref", scope_ref="scope-ref", state_path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(data).lower()
    assert "password" not in text
    assert "secret" not in text
    assert "username" not in text
