"""Deterministic detection/CVE intelligence primitives for RouterScan 1.4.

Pure data transformations only. No network activity, credential handling, or
scope expansion is performed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Iterable, Mapping

DETECTOR_VERSION = "1.4.0"


@dataclass(frozen=True)
class DetectionEvidence:
    source: str
    vendor: str
    model: str | None = None
    strength: float = 0.0


@dataclass(frozen=True)
class DetectionResult:
    vendor: str
    model: str | None
    score: float
    confidence: str
    detector_version: str = DETECTOR_VERSION
    evidence: tuple[DetectionEvidence, ...] = ()


def calibrate_confidence(raw_score: float, *, evidence_count: int = 0) -> tuple[float, str]:
    """Clamp a score and apply a small evidence-count calibration bonus."""
    score = max(0.0, min(1.0, float(raw_score)))
    score = min(0.99, score + min(max(0, evidence_count), 3) * 0.025)
    level = "high" if score >= 0.80 else "medium" if score >= 0.50 else "low"
    return round(score, 3), level


def fingerprint_id(vendor: str, model: str | None, detector_version: str = DETECTOR_VERSION) -> str:
    """Return a stable opaque fingerprint ID for detector regression tracking."""
    canonical = "|".join((vendor.strip().lower(), (model or "").strip().lower(), detector_version))
    return sha256(canonical.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class VulnerabilityRecord:
    cve_id: str
    vendor: str
    product: str
    version: str | None = None
    cvss: float | None = None
    kev: bool = False
    epss: float | None = None
    source: str = "local"

    def normalized(self) -> "VulnerabilityRecord":
        cve = self.cve_id.strip().upper()
        vendor = re.sub(r"\s+", " ", self.vendor.strip().lower())
        product = re.sub(r"\s+", " ", self.product.strip().lower())
        version = self.version.strip() if self.version else None
        cvss = None if self.cvss is None else max(0.0, min(10.0, float(self.cvss)))
        epss = None if self.epss is None else max(0.0, min(1.0, float(self.epss)))
        return VulnerabilityRecord(cve, vendor, product, version, cvss, bool(self.kev), epss, self.source)


def normalize_vulnerabilities(records: Iterable[VulnerabilityRecord]) -> tuple[VulnerabilityRecord, ...]:
    """Normalize and deterministically deduplicate vulnerability intelligence."""
    unique: dict[tuple[str, str, str, str | None], VulnerabilityRecord] = {}
    for record in records:
        item = record.normalized()
        key = (item.cve_id, item.vendor, item.product, item.version)
        unique[key] = item
    return tuple(unique[key] for key in sorted(unique))


def risk_score(record: VulnerabilityRecord) -> float:
    """Compute bounded explainable priority from CVSS, KEV and EPSS."""
    item = record.normalized()
    score = (item.cvss or 0.0) / 10.0 * 0.55
    score += (item.epss or 0.0) * 0.30
    if item.kev:
        score += 0.15
    return round(min(1.0, max(0.0, score)), 3)


def risk_tier(score: float) -> str:
    score = max(0.0, min(1.0, float(score)))
    return "critical" if score >= 0.85 else "high" if score >= 0.65 else "medium" if score >= 0.35 else "low"


@dataclass(frozen=True)
class DifferentialResult:
    status: str
    previous_fingerprint: str | None
    current_fingerprint: str | None


def differential(previous: Mapping[str, object] | None, current: Mapping[str, object] | None) -> DifferentialResult:
    """Compare sanitized result identities without exposing raw target values."""
    old = None if previous is None else str(previous.get("fingerprint") or "") or None
    new = None if current is None else str(current.get("fingerprint") or "") or None
    if old is None and new is not None:
        status = "NEW"
    elif old is not None and new is None:
        status = "RESOLVED"
    elif old == new:
        status = "UNCHANGED"
    else:
        status = "CHANGED"
    return DifferentialResult(status, old, new)
