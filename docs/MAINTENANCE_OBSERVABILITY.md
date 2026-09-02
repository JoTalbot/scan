# Maintenance observability

RouterScan 1.3.x keeps observability privacy-safe, bounded, and optional.

The production implementation uses a bounded JSONL sink with size-based rotation. It is configured through `SCAN_OBSERVABILITY_FILE`, `SCAN_OBSERVABILITY_MAX_BYTES`, and `SCAN_OBSERVABILITY_ROTATIONS`.

## Guarantees

- event names and labels are bounded;
- the active sink rotates before exceeding the configured byte budget;
- only a bounded number of rotated files are retained;
- sensitive keys and values are redacted before serialization;
- sink failures never change scan behavior;
- raw targets, authorization material, credentials, inventory, and HTTP bodies are never persisted.

External metrics backends remain optional and are not required for scanning.

## Baselines and SLOs

For the first production baseline, track aggregate job, shard, detection, error, duration, and sink-health measurements. Thresholds must be derived from observed production distributions rather than guessed values.

Initial SLO candidates are operational hypotheses until a meaningful production sample exists:

- job completion success rate;
- shard recovery success rate;
- detection pipeline error rate;
- telemetry write failure rate;
- dashboard/API availability.

Thresholds become automated alerts only after review and documentation.
