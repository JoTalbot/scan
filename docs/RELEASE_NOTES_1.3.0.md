# RouterScan 1.3.0

## Production release

RouterScan 1.3.0 consolidates the hardening work required for production-oriented operation: durable resumable execution, deterministic multi-signal detection, cross-version CI gates, repository policy checks, privacy-safe observability, and sanitized public artifacts.

## Included

- Durable job and shard state with idempotent retries.
- Job completion only after all declared shards complete.
- Bounded concurrency and TCP port validation.
- Multi-signal router detection and regression coverage.
- Python 3.10, 3.11, and 3.12 CI coverage.
- Repository secret/policy regression checks.
- Privacy-safe, opt-in JSONL telemetry for job, shard, and detection lifecycle events.
- Aggregate-only dashboard observability endpoint.
- Integration coverage for authorization, recovery, retry, and synchronization behavior.
- Public report and status artifacts sanitized to exclude live targets and credential evidence.

## Security posture

Active probing remains fail-closed and requires explicit authorization and scope references. Telemetry and public-facing outputs do not contain credentials, tokens, raw targets, inventories, HTTP headers, authorization references, or private keys.

## Release gate

The previous P0 blocker `SCAN-SEC-004` is resolved. Public findings were removed from the public report/status artifacts and regression tests now prevent reintroduction of target addresses and credential evidence.

## Deferred by design

External metrics backends, alert thresholds/SLOs, and dashboard distribution charts remain backlog items until deployment scale and production baselines justify them.
