# RouterScan 1.3.x maintenance

## Production rule

Do not weaken authorization, public-data sanitization, resumable execution, shard idempotency, or privacy-safe telemetry to make maintenance changes easier.

## Completed maintenance batch

- **SCAN-OBS-003:** bounded and rotating local JSONL telemetry sink.
- **SCAN-OBS-004:** production baseline and alert/SLO promotion policy.
- **SCAN-DASH-003:** aggregate dashboard metrics and privacy-safe dashboard view.

These maintenance enhancements do not change the fail-closed scanning boundary.

## Batch workflow

Implement compatible maintenance changes together, run unit/integration tests and repository policy/security gates, inspect public artifacts, then release as the next 1.3.x patch when justified.
