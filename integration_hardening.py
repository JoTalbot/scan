"""End-to-end validation helpers for RouterScan 1.4 platform primitives.

This module composes existing bounded primitives only. It never authorizes a
scope, performs network I/O, or stores raw targets.
"""
from __future__ import annotations

from agent_registry import AgentRegistry
from detection_intelligence import differential, fingerprint_id
from evidence import EvidenceItem
from scan_profiles import get_profile


def validate_pipeline(*, profile_name: str, finding_id: str, detector_version: str,
                      signal_sources: tuple[str, ...], probe_name: str,
                      worker_id: str, capabilities: tuple[str, ...]) -> dict[str, object]:
    profile = get_profile(profile_name)
    registry = AgentRegistry()
    registry.register(worker_id, capabilities)
    evidence = EvidenceItem.create(
        finding_id=finding_id,
        signal_sources=signal_sources,
        probe_name=probe_name,
        detector_version=detector_version,
    )
    return {
        "profile": profile.name,
        "profile_limits": profile.limits(),
        "evidence_id": evidence.evidence_id,
        "fingerprint_id": fingerprint_id("unknown", None, detector_version),
        "worker": registry.select(capabilities),
        "differential_example": differential(None, {"fingerprint": evidence.evidence_id}).status,
    }
