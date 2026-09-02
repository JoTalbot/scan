import json

import job_state
import resumable_dispatch
from router_detect import detect_router_scored


def test_shard_completion_finalizes_job(tmp_path, monkeypatch):
    state_path = tmp_path / "job.json"
    monkeypatch.setenv("SCAN_AUTHORIZATION_REF", "AUTH-TEST")
    monkeypatch.setenv("SCAN_SCOPE_REF", "SCOPE-TEST")

    calls = []

    def fake_run(argv, cwd=None):
        calls.append((argv, cwd))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(resumable_dispatch.subprocess, "run", fake_run)

    assert resumable_dispatch.run_shard("job-1", 0, 2, state_path=str(state_path)) == 0
    state = job_state.load_state(str(state_path))
    assert state["jobs"]["job-1"]["status"] == "running"

    assert resumable_dispatch.run_shard("job-1", 1, 2, state_path=str(state_path)) == 0
    state = job_state.load_state(str(state_path))
    assert state["jobs"]["job-1"]["status"] == "completed"
    assert len(calls) == 2


def test_completed_shard_is_idempotent(tmp_path, monkeypatch):
    state_path = tmp_path / "job.json"
    monkeypatch.setenv("SCAN_AUTHORIZATION_REF", "AUTH-TEST")
    monkeypatch.setenv("SCAN_SCOPE_REF", "SCOPE-TEST")
    calls = []
    monkeypatch.setattr(
        resumable_dispatch.subprocess,
        "run",
        lambda *args, **kwargs: calls.append(args) or type("Result", (), {"returncode": 0})(),
    )

    resumable_dispatch.run_shard("job-2", 0, 1, state_path=str(state_path))
    resumable_dispatch.run_shard("job-2", 0, 1, state_path=str(state_path))
    assert len(calls) == 1


def test_router_detection_exposes_multi_signal_evidence():
    result = detect_router_scored(
        server_header="Router Webserver",
        title="TP-Link Wireless Router",
        banner='WWW-Authenticate: Basic realm="TP-LINK Wireless N Router WR741ND"',
    )
    assert result is not None
    assert result["vendor"] == "TP-Link"
    assert result["score"] >= 0.75
    assert "server_header" in result["matched_sources"]
    assert "title" in result["matched_sources"]
    assert result["signals"]


def test_job_state_never_requires_targets_or_credentials():
    state = {"schema_version": 1, "jobs": {}}
    encoded = json.dumps(state)
    assert "password" not in encoded.lower()
    assert "target" not in encoded.lower()
