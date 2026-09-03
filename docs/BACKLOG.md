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
- [x] SCAN-DET-003 Add deterministic confidence calibration and detector benchmark corpus primitives.
- [x] SCAN-DET-004 Add versioned opaque fingerprints and false-positive regression primitives.
- [x] SCAN-CVE-002 Add normalized vendor/product/version vulnerability intelligence primitives.
- [x] SCAN-CVE-003 Add bounded CVSS/KEV/EPSS-aware risk prioritization.
- [x] SCAN-DIFF-001 Add differential scan result classification: NEW, CHANGED, RESOLVED, UNCHANGED.
- [x] SCAN-CI-001 Make tests a required CI gate.
- [x] SCAN-CI-002 Fail pipeline stages loudly instead of silently swallowing operational failures.
- [x] SCAN-DOC-001 Generate status/report views from canonical state and sanitized result data.
- [x] SCAN-REL-002 Add bounded scheduler primitives with priorities, backpressure and graceful shutdown.
- [x] SCAN-REL-003 Add process-safe lease/heartbeat primitives for checkpoint/resume orchestration.
- [x] SCAN-REL-004 Add deterministic task IDs and queue deduplication.
- [x] SCAN-REL-005 Add worker lease expiry and reassignment primitives.
- [x] SCAN-REL-006 Add bounded retry budgets and circuit-breaker primitives.
- [x] SCAN-EVID-001 Evidence model linking findings to signals, probes and detector versions.
- [x] SCAN-PROF-001 Explicit scan profiles with bounded probe/risk policies.

## P2

- [x] SCAN-OBS-001 Add durable privacy-safe telemetry for jobs, shards and detection outcomes.
- [x] SCAN-OBS-002 Add worker/job telemetry visibility to the dashboard through `/api/observability` with aggregate counts only.
- [x] SCAN-OBS-003 Add bounded/rotating JSONL telemetry storage with configurable byte and retention limits.
- [x] SCAN-OBS-004 Define production alert/SLO candidates and require observed baselines before promoting thresholds to automated gates.
- [x] SCAN-DASH-003 Add a privacy-safe dashboard view for aggregate job/shard/detection/duration charts.
- [x] SCAN-DOC-002 Refresh README against the current implementation.
- [x] SCAN-REL-001 Establish release/versioning rules.
- [x] SCAN-TEST-001 Add integration tests for pipeline recovery and synchronization.
- [x] SCAN-AGENT-002 Capability registry, worker health scoring and task leasing.
- [x] SCAN-PLUG-001 Versioned plugin interfaces for fingerprints, probes and intelligence providers.
- [x] SCAN-PERF-001 Repeatable load/performance benchmark suite.
- [x] SCAN-DASH-004 Historical operational analytics without exposing raw targets.

## Security follow-ups

- [x] SCAN-SEC-004 Sanitize/remove existing public findings from generated reports/history where practical.
- [x] SCAN-SEC-005 Remove credential material from dashboard/API responses and expose classification/counts only.
- [x] SCAN-SEC-006 Ensure synchronization never pushes generated credential evidence to a public branch.
- [x] SCAN-SEC-007 Apply the authorization gate to the HTTP and browser audit entrypoints.
- [x] SCAN-SEC-008 Add a CI check for sensitive-field names and known credential-artifact paths in tracked files.
- [x] SCAN-SEC-009 Add SSRF/DNS-rebinding defenses for outbound probes.
- [x] SCAN-SEC-010 Enforce strict private/link-local/reserved network policy.
- [x] SCAN-SEC-011 Enforce response-size, decompression, timeout and resource-exhaustion limits.
- [x] SCAN-SEC-012 Add malformed protocol and redirect abuse regression coverage.

## Platform

- [x] SCAN-EVID-001 Evidence model linking findings to signals, probes and detector versions.
- [x] SCAN-PROF-001 Explicit scan profiles with bounded probe/risk policies.
- [x] SCAN-AGENT-002 Capability registry, worker health scoring and task leasing.
- [x] SCAN-PLUG-001 Versioned plugin interfaces for fingerprints, probes and intelligence providers.
- [x] SCAN-PERF-001 Repeatable load/performance benchmark suite.
- [x] SCAN-DASH-004 Historical operational analytics without exposing raw targets.

## Batch rule

Each hardening batch is executed in ordered iterations. A later iteration must not weaken an earlier security gate. Product improvements discovered during implementation are added here before implementation rather than silently becoming scope.
