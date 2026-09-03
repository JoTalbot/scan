#!/usr/bin/env python3
"""Stable, network-free plugin contracts for RouterScan extensions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Mapping
import re

API_VERSION = "1.0"
_VERSION = re.compile(r"^(\d+)\.(\d+)$")

def compatible_version(version: str, api_version: str = API_VERSION) -> bool:
    m, a = _VERSION.fullmatch(version), _VERSION.fullmatch(api_version)
    return bool(m and a and m.group(1) == a.group(1))

def validate_metadata(metadata: Mapping[str, str]) -> dict[str, str]:
    if len(metadata) > 32:
        raise ValueError("too many plugin metadata fields")
    result = {}
    for key, value in metadata.items():
        if len(str(key)) > 64 or len(str(value)) > 256:
            raise ValueError("plugin metadata field is too large")
        result[str(key)] = str(value)
    return result

@dataclass(frozen=True)
class PluginInfo:
    name: str
    version: str
    api_version: str = API_VERSION
    metadata: Mapping[str, str] | None = None
    def validate(self) -> "PluginInfo":
        if not self.name or not compatible_version(self.api_version):
            raise ValueError("incompatible plugin API version")
        if not _VERSION.fullmatch(self.version):
            raise ValueError("plugin version must be major.minor")
        validate_metadata(self.metadata or {})
        return self

class FingerprintPlugin(Protocol):
    info: PluginInfo
    def fingerprint(self, signals: Mapping[str, str]) -> Mapping[str, object]: ...

class ProbePlugin(Protocol):
    info: PluginInfo
    def probe(self, context: Mapping[str, object]) -> Mapping[str, object]: ...

class IntelligencePlugin(Protocol):
    info: PluginInfo
    def lookup(self, vendor: str, product: str, version: str) -> Mapping[str, object]: ...
