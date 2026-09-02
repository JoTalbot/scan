# RouterScan Hardening Backlog

This backlog is the canonical implementation order for the current hardening cycle.

## P0

- No open P0 blockers. `SCAN-SEC-004` was closed by sanitizing public report/status artifacts and adding regression coverage.

## P1

- [x] SCAN-ARCH-001 Make `PROJECT_STATE.json` the machine-readable source of truth.
- [x] SCAN-ARCH-002 Make distributed jobs resumable and shard-idempotent.
- [x] SCAN-ARCH-003 Replace hard-coded scanner limits with central configuration and bounded concurrency.
- [x] SCAN-DET-001 Add multi-signal router detection scoring.
- [x] SCAN-DET-002 Expand router detection regression coverage.
- [x] SCAN-CI-001 Make tests a required CI gate. Full pytest workflow is present; repository branch protection still needs to require it.
- [x] SCAN-CI-002 Fail pipeline stages loudly instead of silently swallowing operational failures.
- [x] SCAN-DOC-001 Generate status/report views from canonical state and sanitized result data.

## P2

- [x] SCAN-OBS-001 Add durable privacy-safe telemetry for jobs, shards and detection outcomes.
- [x] SCAN-OBS-002 Add worker/job telemetry visibility to the dashboard through `/api/observability` with aggregate counts only.
- [x] SCAN-OBS-003 Add bounded/rotating JSONL telemetry storage with configurable byte and retention limits.
- [x] SCAN-OBS-004 Define production alert/SLO candidates and require observed baselines before promoting thresholds to automated gates.
- [x] SCAN-DASH-003 Add a privacy-safe dashboard view for aggregate job/shard/detection/duration charts.
- [x] SCAN-DOC-002 Refresh README against the current implementation.
- [x] SCAN-REL-001 Establish release/versioning rules.
- [x] SCAN-TEST-001 Add integration tests for pipeline recovery and synchronization.

## Security follow-ups

- [x] SCAN-SEC-004 Sanitize/remove existing public findings from generated reports/history where practical.
- [x] SCAN-SEC-005 Remove credential material from dashboard/API responses and expose classification/counts only.
- [x] SCAN-SEC-006 Ensure synchronization never pushes generated credential evidence to a public branch.
- [x] SCAN-SEC-007 Apply the authorization gate to the HTTP and browser audit entrypoints.
- [x] SCAN-SEC-008 Add a CI check for sensitive-field names and known credential-artifact paths in tracked files.

## Product/architecture follow-ups

- [x] SCAN-ARCH-004 Make remote shard completion observable before marking a shard complete.

## Batch rule

Each hardening batch is executed in ordered iterations. A later iteration must not weaken an earlier security gate. Product improvements discovered during implementation are added here before implementation rather than silently becoming scope.
