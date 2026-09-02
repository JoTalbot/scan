import json
from pathlib import Path

import observability


def test_jsonl_sink_rotates_and_bounds_files(tmp_path):
    path = tmp_path / "events.jsonl"
    sink = observability.JsonlSink(path, max_bytes=180, rotations=2)
    for index in range(12):
        sink.emit("job.completed", job_id=f"job-{index}", target=f"10.0.0.{index}")

    files = [path] + [path.with_name(f"events.jsonl.{i}") for i in range(1, 3)]
    existing = [item for item in files if item.exists()]
    assert existing
    assert len(existing) <= 3
    assert all(item.stat().st_size <= 220 for item in existing)
    assert path.with_name("events.jsonl.3").exists() is False

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines
    payload = json.loads(lines[-1])
    assert payload["target"] == "[REDACTED]"


def test_jsonl_sink_invalid_limits_fall_back_to_safe_defaults(tmp_path):
    sink = observability.JsonlSink(tmp_path / "events.jsonl", max_bytes="bad", rotations="bad")
    assert sink.max_bytes == observability._DEFAULT_MAX_BYTES
    assert sink.rotations == observability._DEFAULT_ROTATIONS
