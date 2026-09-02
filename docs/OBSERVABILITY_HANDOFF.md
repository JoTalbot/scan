# Observability Handoff

## Completed in this batch

- Structured JSONL event sink with opt-in activation.
- Recursive redaction of sensitive fields and bounded strings/labels.
- Job lifecycle telemetry: start and resume-skip, completion.
- Shard lifecycle telemetry: start, skip, success, failure.
- Detection telemetry contract limited to vendor/model/device type, score and evidence-source names.
- Dashboard aggregate endpoint: `GET /api/observability`.
- Regression tests for privacy and lifecycle behavior.
- Project state and backlog updated to version `1.3.0-observability`.

## Production acceptance criteria

- Telemetry path is outside public export/synchronization paths.
- `SCAN_OBSERVABILITY_FILE` is writable by the service account.
- `/api/observability` is reachable only where the dashboard itself is authorized to be reachable.
- No telemetry event contains a raw target, target inventory, authorization value, credential, password, token or HTTP header.
- CI remains green on Python 3.10, 3.11 and 3.12.

## Next engineering phase

The remaining backlog is documentation/release hardening plus integration coverage. External metrics backends and alert thresholds remain intentionally deferred until deployment baselines exist.
