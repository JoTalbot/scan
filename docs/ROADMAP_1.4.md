# RouterScan 1.4 Roadmap

## Goal
Move RouterScan from a production-ready 1.3.x maintenance baseline toward a resilient, measurable, high-confidence scanning platform.

## P1 reliability
- SCAN-REL-002: scheduler with bounded concurrency, priorities, backpressure and graceful shutdown.
- SCAN-REL-003: process/server checkpoint and resume guarantees.
- SCAN-REL-004: cross-worker task deduplication and deterministic task IDs.
- SCAN-REL-005: worker heartbeat, lease expiry and shard reassignment.
- SCAN-REL-006: circuit breakers and bounded retry budgets for external dependencies.

## P1 detection and intelligence
- SCAN-DET-003: confidence calibration and detector benchmark corpus.
- SCAN-DET-004: fingerprint versioning and false-positive regression corpus.
- SCAN-CVE-002: normalized vendor/product/version vulnerability intelligence.
- SCAN-CVE-003: CVSS/KEV/EPSS-aware risk prioritization.
- SCAN-DIFF-001: differential scan results: NEW, CHANGED, RESOLVED, UNCHANGED.

## P1 security hardening
- SCAN-SEC-005: SSRF and DNS-rebinding defenses for all outbound probes.
- SCAN-SEC-006: strict network/range policy for private, link-local and reserved addresses.
- SCAN-SEC-007: response-size, decompression, timeout and resource-exhaustion limits.
- SCAN-SEC-008: malformed protocol and redirect abuse regression suite.

## P2 platform
- SCAN-EVID-001: evidence model linking findings to signals, probes and detector versions.
- SCAN-PROF-001: explicit scan profiles with bounded probe/risk policies.
- SCAN-AGENT-002: capability registry, worker health scoring and task leasing.
- SCAN-PLUG-001: versioned plugin interfaces for fingerprints, probes and intelligence providers.
- SCAN-PERF-001: repeatable load/performance benchmark suite.
- SCAN-DASH-004: historical operational analytics without exposing raw targets.

## Product improvements discovered during implementation
- Keep all product changes proposed and tracked before implementation.
- Never silently widen scan authorization or scope.
- Prefer safe defaults, bounded resource use and explainable findings.
