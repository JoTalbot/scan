# Production observability baseline

RouterScan records only aggregate operational telemetry. This document defines the first baseline contract before alerting is promoted to an SLO gate.

## Measures

- jobs: started, completed, failed
- shards: started, completed, retried, failed
- detections: count and confidence distribution
- duration: job/shard/detection operation duration
- telemetry: emitted, dropped, sink failures

## Alerting rule

No fixed production threshold is enabled by default. Thresholds must be derived from observed production distributions and reviewed together with false-positive impact.

## Privacy

Dashboards and metrics must remain aggregate. They must not expose target addresses, authorization references, credentials, raw HTTP artifacts, or target inventories.
