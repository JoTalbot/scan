# RouterScan Hardening Backlog

This backlog is the canonical implementation order for the current hardening cycle.

## P0

- [x] SCAN-SEC-001 Public reports never contain discovered passwords. Foundation sanitizer and public-report CLI added; credential export is excluded from Git. Remaining: remove legacy public/API exposure paths.
- [x] SCAN-SEC-002 Active probing requires an explicit authorization reference/target policy. Pipeline and scan entrypoints are fail-closed; shared authorization contract added.
- [x] SCAN-SEC-003 CI regression test blocks credential/secret leakage. Security regression workflow and static regression tests added.
- [ ] SCAN-SEC-004 Existing public findings are sanitized or removed from generated reports/history where practical.

## P1

- [x] SCAN-ARCH-001 Make `PROJECT_STATE.json` the machine-readable source of truth.
- [x] SCAN-ARCH-002 Make distributed jobs resumable and shard-idempotent.
- [x] SCAN-ARCH-003 Replace hard-coded scanner limits with central configuration and bounded concurrency.
- [x] SCAN-DET-001 Add multi-signal router detection scoring.
- [x] SCAN-DET-002 Expand router detection regression coverage.
- [x] SCAN-CI-001 Make tests a required CI gate. Full pytest workflow is present; repository branch protection still needs to require it.
- [x] SCAN-CI-002 Fail pipeline stages loudly instead of silently swallowing operational failures.
- [ ] SCAN-DOC-001 Generate status/report views from canonical state and sanitized result data.

## P2

- [x] SCAN-OBS-001 Add durable privacy-safe telemetry for jobs, shards and detection outcomes.
- [x] SCAN-OBS-002 Add worker/job telemetry visibility to the dashboard through `/api/observability` with aggregate counts only.
- [ ] SCAN-DOC-002 Refresh README against the current implementation.
- [ ] SCAN-REL-001 Establish release/versioning rules.
- [ ] SCAN-TEST-001 Add integration tests for pipeline recovery and synchronization.

## Newly discovered security follow-ups

- [x] SCAN-SEC-005 Remove credential material from dashboard/API responses and expose classification/counts only.
- [x] SCAN-SEC-006 Ensure synchronization never pushes generated credential evidence to a public branch.
- [x] SCAN-SEC-007 Apply the authorization gate to the HTTP and browser audit entrypoints.
- [x] SCAN-SEC-008 Add a CI check for sensitive-field names and known credential-artifact paths in tracked files.

## Newly discovered product/architecture follow-ups

- [x] SCAN-ARCH-004 Make remote shard completion observable before marking a shard complete.
- [ ] SCAN-OBS-003 Replace JSONL storage with a bounded/rotating metrics backend when deployment scale requires it.
- [ ] SCAN-OBS-004 Add alert thresholds and SLOs after production traffic baselines exist.
- [ ] SCAN-DASH-003 Add dashboard charts for shard duration, failure rate and detection confidence distributions.

## Batch rule

Each hardening batch is executed in ordered iterations. A later iteration must not weaken an earlier security gate. Product improvements discovered during implementation are added here before implementation rather than silently becoming scope.
