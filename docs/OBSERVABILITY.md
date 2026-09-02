# Observability

## Scope

RouterScan now has a dependency-free, privacy-safe telemetry layer for job, shard and detection lifecycle events.

### Event contract

- `job.started` — a resumable job entered running state.
- `job.resume_skipped` — a completed job was invoked again and no work was started.
- `shard.started` — a shard is about to execute.
- `shard.skipped` — an already-completed shard was skipped.
- `shard.completed` — a shard finished successfully and its durable marker was persisted.
- `shard.failed` — the scan subprocess returned a non-zero exit code.
- `job.completed` — all declared shards are complete.
- `detection.result` — vendor/model/device type, confidence, score and evidence-source names only.
- `detection.none` — no router signature was selected.

## Privacy boundary

Telemetry never records raw targets, target inventories, HTTP headers, authorization references, credentials, passwords, tokens, API keys or private keys. Sensitive field names are redacted recursively and strings are bounded.

The telemetry sink is opt-in. Set `SCAN_OBSERVABILITY_FILE` to a JSONL path to enable it. With no value, event emission is a no-op.

## Dashboard

`GET /api/observability` returns aggregate event counts and whether telemetry is enabled. It deliberately does not return raw JSONL events.

Example response shape:

```json
{"enabled":true,"events":42,"event_types":{"job.started":2,"shard.completed":8}}
```

## Operations

1. Set `SCAN_OBSERVABILITY_FILE` to a local writable path outside public exports.
2. Ensure the telemetry file is excluded from public synchronization/export paths.
3. Inspect `/api/observability` for aggregate lifecycle health.
4. Investigate repeated `shard.failed` events before retrying production work.
5. Add SLO/alert thresholds only after real production baselines exist.

## Deliberate non-goals

This phase does not add an external metrics dependency, remote telemetry transport, raw event API, or automatic alerting. Those are tracked separately so operational complexity is earned by actual scale rather than summoned by optimism.
