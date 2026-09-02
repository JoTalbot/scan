# RouterScan Hardening Backlog

This backlog is the canonical implementation order for the current hardening cycle.

## P0

- [x] SCAN-SEC-001 Public reports never contain discovered passwords. Foundation sanitizer and public-report CLI added; credential export is now excluded from Git. Remaining: remove legacy public/API exposure paths.
- [x] SCAN-SEC-002 Active probing requires an explicit authorization reference/target policy. Pipeline and scan entrypoints are fail-closed; shared authorization contract added.
- [x] SCAN-SEC-003 CI regression test blocks credential/secret leakage. Security regression workflow and static regression tests added.
- [ ] SCAN-SEC-004 Existing public findings are sanitized or removed from generated reports/history where practical.

## P1

- [x] SCAN-ARCH-001 Make `PROJECT_STATE.json` the machine-readable source of truth.
- [ ] SCAN-ARCH-002 Make distributed jobs resumable and shard-idempotent. Durable job/shard state and a fail-closed resumable shard executor are implemented; legacy `dispatch.py` still needs to route every distributed scan launch through the executor before this item can close.
- [x] SCAN-ARCH-003 Replace hard-coded scanner limits with central configuration and bounded concurrency.
- [x] SCAN-DET-001 Add multi-signal router detection scoring. Detection now combines independent server-header, realm, title and banner evidence with deterministic scoring, agreement bonuses and trap suppression.
- [x] SCAN-DET-002 Expand router detection regression coverage. Added a detection matrix covering strong signals, cross-field agreement, generic servers, traps, model extraction and determinism.
- [x] SCAN-CI-001 Make tests a required CI gate. Full pytest workflow is now present; repository branch protection still needs to require it.
- [x] SCAN-CI-002 Fail pipeline stages loudly instead of silently swallowing operational failures.
- [ ] SCAN-DOC-001 Generate status/report views from canonical state and sanitized result data.

## P2

- [ ] SCAN-OBS-001 Add durable metrics for jobs/workers.
- [ ] SCAN-OBS-002 Add worker health and shard progress to the dashboard.
- [ ] SCAN-DOC-002 Refresh README against the current implementation.
- [ ] SCAN-REL-001 Establish release/versioning rules.
- [ ] SCAN-TEST-001 Add integration tests for pipeline recovery and synchronization.

## Newly discovered security follow-ups

- [x] SCAN-SEC-005 Remove credential material from dashboard/API responses and expose classification/counts only.
- [x] SCAN-SEC-006 Ensure synchronization never pushes generated credential evidence to a public branch. Sync now requires an explicit non-main branch and stages only approved public export paths.
- [x] SCAN-SEC-007 Apply the authorization gate to the HTTP and browser audit entrypoints; no dedicated SSH/Telnet audit entrypoints were found in the active tree, so no separate active gate was required there.
- [x] SCAN-SEC-008 Add a CI check for sensitive-field names and known credential-artifact paths in tracked files.

## Newly discovered product/architecture follow-ups

- [ ] SCAN-ARCH-004 Make remote shard completion observable before marking a shard complete. SSH dispatch currently backgrounds the remote command, so process exit alone cannot prove the remote scan finished; use synchronous execution or an explicit completion sentinel/receipt before treating the shard as successful.

## Batch rule

Each hardening batch is executed in ordered iterations. A later iteration must not weaken an earlier security gate. Product improvements discovered during implementation are added here before implementation rather than silently becoming scope.
