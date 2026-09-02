import json

import observability


def test_sanitize_redacts_sensitive_fields_and_bounds_values():
    payload = observability.sanitize({
        "authorization_ref": "secret-auth",
        "scope_ref": "secret-scope",
        "target_inventory": ["10.0.0.1"],
        "vendor": "MikroTik",
        "long": "x" * 400,
    })
    assert payload["authorization_ref"] == "[REDACTED]"
    assert payload["scope_ref"] == "[REDACTED]"
    assert payload["target_inventory"] == "[REDACTED]"
    assert payload["vendor"] == "MikroTik"
    assert len(payload["long"]) == 256


def test_jsonl_sink_emits_structured_event_without_secrets(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    sink = observability.JsonlSink(path)
    event = sink.emit(
        "shard.completed",
        job_id="job-1",
        shard=2,
        authorization_ref="auth-secret",
        target="192.0.2.1",
        vendor="TP-Link",
    )
    assert event["event"] == "shard.completed"
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["job_id"] == "job-1"
    assert row["authorization_ref"] == "[REDACTED]"
    assert row["target"] == "[REDACTED]"
    assert row["vendor"] == "TP-Link"


def test_safe_id_removes_unbounded_label_characters():
    assert observability.safe_id("job/one\nwith spaces") == "job_one_with_spaces"
