# RouterScan Hardening Backlog

This backlog is the canonical implementation order for the current hardening cycle.

## P0

- No open P0 blockers.

## P1

- [x] SCAN-ARCH-001 Make `PROJECT_STATE.json` the machine-readable source of truth.
- [x] SCAN-ARCH-002 Make distributed jobs resumable and shard-idempotent.
- [x] SCAN-ARCH-003 Replace hard-coded scanner limits with central configuration and bounded concurrency.
- [x] SCAN-DET-001 Add multi-signal router detection scoring.
- [x] SCAN-DET-002 Expand router detection regression coverage.
- [x] SCAN-CI-001 Make tests a required CI gate.
- [x] SCAN-CI-002 Fail pipeline stages loudly instead of silently swallowing operational failures.
- [x] SCAN-DOC-001 Generate status/report views from canonical state and sanitized result data.
- [x] SCAN-REL-002 Add bounded scheduler primitives with priorities, backpressure and graceful shutdown.
- [x] SCAN-REL-003 Add process-safe lease/heartbeat primitives for checkpoint/resume orchestration.
- [x] SCAN-REL-004 Add deterministic task IDs and queue deduplication.
- [x] SCAN-REL-005 Add worker lease expiry and reassignment primitives.
- [x] SCAN-REL-006 Add bounded retry budgets and circuit-breaker primitives.

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
- [ ] SCAN-SEC-009 SSRF/DNS-rebinding defenses for all outbound probes.
- [ ] SCAN-SEC-010 Strict private/link-local/reserved network policy.
- [ ] SCAN-SEC-011 Response-size, decompression, timeout and resource-exhaustion limits.
- [ ] SCAN-SEC-012 Malformed protocol and redirect abuse regression suite.

## Detection/intelligence

- [ ] SCAN-DET-003 Confidence calibration and detector benchmark corpus.
- [ ] SCAN-DET-004 Fingerprint versioning and false-positive regression corpus.
- [ ] SCAN-CVE-002 Normalized vendor/product/version vulnerability intelligence.
- [ ] SCAN-CVE-003 CVSS/KEV/EPSS-aware risk prioritization.
- [ ] SCAN-DIFF-001 Differential scan results: NEW, CHANGED, RESOLVED, UNCHANGED.

## Platform

- [ ] SCAN-EVID-001 Evidence model linking findings to signals, probes and detector versions.
- [ ] SCAN-PROF-001 Explicit scan profiles with bounded probe/risk policies.
- [ ] SCAN-AGENT-002 Capability registry, worker health scoring and task leasing.
- [ ] SCAN-PLUG-001 Versioned plugin interfaces for fingerprints, probes and intelligence providers.
- [ ] SCAN-PERF-001 Repeatable load/performance benchmark suite.
- [ ] SCAN-DASH-004 Historical operational analytics without exposing raw targets.

## Batch rule

Each hardening batch is executed in ordered iterations. A later iteration must not weaken an earlier security gate. Product improvements discovered during implementation are added here before implementation rather than silently becoming scope.
