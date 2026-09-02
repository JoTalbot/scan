# Observability handoff

The pre-observability phase leaves the following stable events available for telemetry work:

- job started / resumed;
- shard started;
- shard skipped because it is already complete;
- shard completed successfully;
- shard failed;
- job completed;
- detection result with vendor, device type, score and evidence-source names.

Telemetry must not copy authorization secrets, credentials, raw target inventories, authentication headers, or other sensitive artifacts into metrics, traces, or logs.

The observability phase should add metrics, structured events and tracing around these lifecycle boundaries without changing their authorization or correctness semantics.
