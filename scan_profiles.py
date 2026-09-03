#!/usr/bin/env python3
"""Explicit, conservative scan profiles that never grant authorization."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ScanProfile:
    name: str
    max_ports: int
    timeout_seconds: float
    concurrency: int
    max_redirects: int
    max_response_bytes: int
    allowed_probe_kinds: tuple[str, ...]
    risk_ceiling: float

    def validate(self) -> "ScanProfile":
        if not self.name or not 1 <= self.max_ports <= 65535:
            raise ValueError("invalid profile or max_ports")
        if not 0.1 <= self.timeout_seconds <= 30.0:
            raise ValueError("timeout_seconds out of bounds")
        if not 1 <= self.concurrency <= 500:
            raise ValueError("concurrency out of bounds")
        if not 0 <= self.max_redirects <= 10:
            raise ValueError("max_redirects out of bounds")
        if not 1024 <= self.max_response_bytes <= 10 * 1024 * 1024:
            raise ValueError("max_response_bytes out of bounds")
        if not self.allowed_probe_kinds:
            raise ValueError("at least one probe kind is required")
        if not 0.0 <= self.risk_ceiling <= 1.0:
            raise ValueError("risk_ceiling out of bounds")
        return self

DEFAULT_SAFE_PROFILE = ScanProfile(
    name="safe-default", max_ports=1024, timeout_seconds=2.0, concurrency=32,
    max_redirects=3, max_response_bytes=1024 * 1024,
    allowed_probe_kinds=("tcp", "http", "fingerprint"), risk_ceiling=0.7,
).validate()

PROFILES = {DEFAULT_SAFE_PROFILE.name: DEFAULT_SAFE_PROFILE}

def get_profile(name: str = "safe-default") -> ScanProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError("unknown scan profile") from exc
