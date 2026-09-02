# RouterScan 1.3.0

## Release candidate

RouterScan 1.3.0 consolidates the hardening work required before production-oriented operation: durable resumable execution, deterministic multi-signal detection, cross-version CI gates, repository policy checks, and privacy-safe observability.

## Included

- Durable job and shard state with idempotent retries.
- Job completion only after all declared shards complete.
- Bounded concurrency and TCP port validation.
- Multi-signal router detection and regression coverage.
- Python 3.10, 3.11, and 3.12 CI coverage.
- Repository secret/policy regression checks.
- Privacy-safe, opt-in JSONL telemetry for job, shard, and detection lifecycle events.
- Aggregate-only dashboard observability endpoint.
- Updated architecture, observability, release checklist, and release policy documentation.
- Integration coverage for authorization, recovery, retry, and synchronization behavior.

## Security posture

Active probing remains fail-closed and requires explicit authorization and scope references. Telemetry and public-facing outputs must not contain credentials, tokens, raw targets, inventories, HTTP headers, or private keys.

## Known blocker

`SCAN-SEC-004` remains open: existing public findings must be sanitized or removed from generated reports/history where practical. Until this P0 item is resolved, 1.3.0 is a release candidate rather than an unrestricted production release.

## Deferred by design

External metrics backends, alert thresholds/SLOs, and dashboard distribution charts remain backlog items until deployment scale and production baselines justify them.
