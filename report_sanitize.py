#!/usr/bin/env python3
"""Helpers for converting internal findings into safe public metadata."""

import hashlib
import ipaddress
import re
from typing import Any, Mapping

_SECRET_KEYS = {
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "cookie", "session", "private_key", "credential",
}


def target_id(value: str, salt: str) -> str:
    """Return a stable non-reversible public identifier for an IP/target."""
    raw = f"{salt}:{value}".encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:20]


def redact_value(key: str, value: Any) -> Any:
    key_norm = re.sub(r"[^a-z0-9_]", "", key.lower())
    if key_norm in {re.sub(r"[^a-z0-9_]", "", x) for x in _SECRET_KEYS}:
        return "REDACTED"
    return value


def public_finding(finding: Mapping[str, Any], *, salt: str) -> dict[str, Any]:
    """Create a public-safe finding without live IPs or credential material."""
    out: dict[str, Any] = {}
    for key, value in finding.items():
        if key.lower() in {"ip", "target_ip", "host", "target"}:
            try:
                ipaddress.ip_address(str(value))
                out["target_id"] = target_id(str(value), salt)
            except ValueError:
                out["target_id"] = target_id(str(value), salt)
            continue
        if key.lower() in {"username", "login"}:
            out["credential_class"] = out.get("credential_class", "verified-credential")
            continue
        safe = redact_value(key, value)
        if safe != "REDACTED":
            out[key] = safe
    if "password" in finding or "passwd" in finding:
        out["credential_class"] = out.get("credential_class", "verified-credential")
    return out
