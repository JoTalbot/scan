# RouterScan Hardening Backlog

This backlog is the canonical implementation order for the current hardening cycle.

## P0

- [ ] SCAN-SEC-001 Public reports never contain discovered passwords.
- [ ] SCAN-SEC-002 Active probing requires an explicit authorization reference/target policy.
- [ ] SCAN-SEC-003 CI regression test blocks credential/secret leakage.
- [ ] SCAN-SEC-004 Existing public findings are sanitized or removed from generated reports/history where practical.

## P1

- [ ] SCAN-ARCH-001 Make `PROJECT_STATE.json` the machine-readable source of truth.
- [ ] SCAN-ARCH-002 Make distributed jobs resumable and shard-idempotent.
- [ ] SCAN-ARCH-003 Replace hard-coded scanner limits with central configuration and bounded concurrency.
- [ ] SCAN-DET-001 Add multi-signal router detection scoring.
- [ ] SCAN-DET-002 Expand router detection regression coverage.
- [ ] SCAN-CI-001 Make tests a required CI gate.
- [ ] SCAN-CI-002 Fail pipeline stages loudly instead of silently swallowing operational failures.
- [ ] SCAN-DOC-001 Generate status/report views from canonical state and sanitized result data.

## P2

- [ ] SCAN-OBS-001 Add durable metrics for jobs/workers.
- [ ] SCAN-OBS-002 Add worker health and shard progress to the dashboard.
- [ ] SCAN-DOC-002 Refresh README against the current implementation.
- [ ] SCAN-REL-001 Establish release/versioning rules.
- [ ] SCAN-TEST-001 Add integration tests for pipeline recovery and synchronization.

## Batch rule

Each hardening batch is executed in ordered iterations. A later iteration must not weaken an earlier security gate. Product improvements discovered during implementation are added here before implementation rather than silently becoming scope.
