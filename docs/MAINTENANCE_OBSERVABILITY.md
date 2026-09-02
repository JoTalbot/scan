# Maintenance observability

RouterScan 1.3.x keeps observability privacy-safe, bounded, and optional.

## Metrics backend

`SCAN_OBSERVABILITY_FILE` may point to a local JSONL sink. Implementations must:

- use bounded event names and labels;
- rotate before the sink exceeds its configured size;
- retain only a bounded number of rotated files;
- never persist raw targets, authorization material, credentials, inventory, or HTTP bodies;
- tolerate a full or unavailable sink without changing scan behavior.

Production defaults should remain conservative. External metrics backends are optional and must not be required for scanning.

## Baselines

For the first production baseline, track only aggregate job, shard, detection, error, and duration measurements. Establish alert thresholds from observed behavior rather than guessed values.

## SLO policy

Initial SLO candidates are operational hypotheses, not release gates. Review after a meaningful production sample:

- job completion success rate;
- shard recovery success rate;
- detection pipeline error rate;
- telemetry write failure rate;
- dashboard/API availability.

Thresholds must be documented before becoming automated alerts.
