# Release readiness checklist

## Security

- [x] Active probing has an explicit authorization reference.
- [x] Target scope is explicit and bounded.
- [x] Credentials and tokens are supplied outside Git.
- [ ] Public reports/history are fully sanitized. **P0 blocker: SCAN-SEC-004.**
- [x] CI policy checks are green.

## Distributed execution

- [x] Every shard has a stable job/shard identity.
- [x] Failed shards remain resumable.
- [x] Successful shards are idempotent on retry.
- [x] The job closes only after all declared shards complete.
- [x] Concurrency and timeout bounds are enforced.

## Detection

- [x] Vendor/model detection has regression coverage.
- [x] Multi-signal evidence is deterministic.
- [x] Confidence scoring remains bounded.
- [x] Known false-positive traps are covered.

## CI and documentation

- [x] Full pytest suite is green on supported Python versions.
- [x] Security regression suite is green.
- [x] Source compilation passes.
- [x] `PROJECT_STATE.json` is valid and current.
- [x] Architecture, observability, security, and release documentation match the implementation.

## Post-release

- [x] Observability work is tracked separately from correctness fixes.
- [x] No production credentials or live findings are copied into public release artifacts.

## Release decision

**Current decision: release candidate only.** Do not publish an unrestricted production release until `SCAN-SEC-004` is closed and the checklist is revalidated.
