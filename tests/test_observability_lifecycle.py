import json

import job_state
import observability


def test_job_shard_lifecycle_emits_safe_events(monkeypatch, tmp_path):
    telemetry = tmp_path / "events.jsonl"
    monkeypatch.setattr(observability, "_DEFAULT_SINK", observability.JsonlSink(telemetry))
    state = tmp_path / "state.json"

    job_state.start_job("job-1", authorization_ref="secret-auth", scope_ref="secret-scope", state_path=str(state))
    job_state.mark_shard_completed("job-1", "0", state_path=str(state))
    job_state.complete_job("job-1", state_path=str(state))

    rows = [json.loads(line) for line in telemetry.read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in rows] == ["job.started", "job.completed"]
    assert all("secret-auth" not in json.dumps(row) for row in rows)
    assert all("secret-scope" not in json.dumps(row) for row in rows)
