# Pre-observability batch

## 1.2.0-pre-observability

- Completed durable shard lifecycle: successful shards are idempotent and a job closes after all declared shards complete.
- Normalized and bounded scan port input before process launch.
- Added regression coverage for shard completion, retry idempotency, multi-signal detection and state hygiene.
- Added a Python 3.10/3.11/3.12 CI matrix.
- Added repository policy checks for obvious credential material and project-state validity.
- Added architecture and release-readiness contracts.
- Established observability as the next phase instead of mixing telemetry into correctness work.
