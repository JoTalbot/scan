"""End-to-end validation helpers for RouterScan 1.4 platform primitives.

This module composes existing bounded primitives only. It never authorizes a
scope, performs network I/O, or stores raw targets.
"""
from __future__ import annotations

from agent_registry import CapabilityRegistry, Worker
from detection_intelligence import differential, fingerprint_id
from evidence import EvidenceSignal, build_evidence
from scan_profiles import get_profile


def validate_pipeline(*, profile_name: str, finding_id: str, detector_version: str,
                      signal_sources: tuple[str, ...], probe_name: str,
                      worker_id: str, capabilities: tuple[str, ...]) -> dict[str, object]:
    profile = get_profile(profile_name)
    registry = CapabilityRegistry()
    registry.register(Worker(worker_id, frozenset(capabilities)))
    signal = EvidenceSignal(
        kind="classified", value_class="router-header", detector_version=detector_version,
        confidence=0.8,
    )
    evidence = build_evidence(
        finding_id, probe_name, "1.0", detector_version, (signal,), source="scanner"
    )[0]
    lease = registry.acquire(evidence.evidence_id, capabilities[0])
    return {
        "profile": profile.name,
        "profile_limits": {
            "max_ports": profile.max_ports,
            "timeout_seconds": profile.timeout_seconds,
            "concurrency": profile.concurrency,
            "max_redirects": profile.max_redirects,
            "max_response_bytes": profile.max_response_bytes,
            "risk_ceiling": profile.risk_ceiling,
        },
        "evidence_id": evidence.evidence_id,
        "fingerprint_id": fingerprint_id("unknown", None, detector_version),
        "worker": lease.worker_id,
        "differential_example": differential(None, {"fingerprint": evidence.evidence_id}).status,
        "signal_sources": tuple(sorted(signal_sources)),
    }
