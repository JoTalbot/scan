# Dashboard charts

Dashboard charts must be derived from aggregate observability events only.

## Required views

1. Job throughput and completion/failure counts.
2. Shard retry and recovery counts.
3. Detection counts by vendor/model/device type.
4. Operation duration distributions.
5. Telemetry sink health.

Charts must use bounded dimensions and must not render live target addresses, authorization references, credentials, target inventories, or raw HTTP evidence.

The dashboard remains read-only with respect to scanning control and preserves the existing fail-closed authorization boundary.
