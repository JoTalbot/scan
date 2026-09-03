#!/usr/bin/env python3
"""Deterministic, privacy-safe evidence records for RouterScan findings."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Iterable

from observability import safe_id


def _stable_id(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()[:32]


@dataclass(frozen=True)
class EvidenceSignal:
    kind: str
    value_class: str
    detector_version: str
    confidence: float = 0.0

    def __post_init__(self):
        if not self.kind or not self.value_class or not self.detector_version:
            raise ValueError("evidence signal fields are required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class EvidenceItem:
    finding_id: str
    signal: EvidenceSignal
    probe_id: str
    probe_version: str
    source: str = "scanner"

    @property
    def evidence_id(self) -> str:
        return _stable_id(self.to_dict())

    def to_dict(self) -> dict:
        data = asdict(self)
        data["finding_id"] = safe_id(self.finding_id)
        data["probe_id"] = safe_id(self.probe_id)
        data["probe_version"] = safe_id(self.probe_version)
        data["source"] = safe_id(self.source)
        data["signal"]["kind"] = safe_id(data["signal"]["kind"])
        data["signal"]["value_class"] = safe_id(data["signal"]["value_class"])
        data["signal"]["detector_version"] = safe_id(data["signal"]["detector_version"])
        return data


def build_evidence(finding_id: str, probe_id: str, probe_version: str,
                   detector_version: str, signals: Iterable[EvidenceSignal],
                   source: str = "scanner") -> list[EvidenceItem]:
    """Create stable evidence without storing raw targets or raw signal values."""
    return [EvidenceItem(finding_id, signal, probe_id, probe_version, source) for signal in signals]
