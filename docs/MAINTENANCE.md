# RouterScan 1.3.x maintenance

## Production rule

Do not weaken authorization, public-data sanitization, resumable execution, shard idempotency, or privacy-safe telemetry to make maintenance changes easier.

## Observability backlog

- **SCAN-OBS-003:** bounded and rotating local metrics sink.
- **SCAN-OBS-004:** alert thresholds and SLOs after production baselines.
- **SCAN-DASH-003:** aggregate dashboard charts without exposing live targets.

These items are maintenance enhancements and do not change the fail-closed scanning boundary.

## Batch workflow

Implement compatible maintenance changes together, run unit/integration tests and repository policy/security gates, inspect public artifacts, then release as the next 1.3.x patch when justified.
