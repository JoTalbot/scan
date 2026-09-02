# RouterScan 1.3.1

## Maintenance release

RouterScan 1.3.1 extends the 1.3.0 production baseline with bounded observability and aggregate dashboard visibility.

### Added

- size-based rotation for the optional JSONL telemetry sink;
- bounded telemetry retention configurable through environment variables;
- aggregate `/api/observability/metrics` endpoint for operational charts;
- privacy-safe observability dashboard with job, shard, detection, and duration views;
- production baseline/SLO policy that avoids guessed alert thresholds.

### Security and reliability

- telemetry remains opt-in and best-effort;
- sensitive fields continue to be redacted recursively;
- raw targets, authorization material, credentials, inventories, and HTTP bodies are excluded from dashboard metrics;
- existing fail-closed authorization, resumable jobs, shard idempotency, and public-artifact sanitization remain unchanged.

### Release gate

The 1.3.1 batch must pass supported Python CI, tests, security regression, repository policy, and public-artifact safety checks before release tagging.
