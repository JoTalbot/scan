"""Fail-closed outbound network policy for RouterScan.

The helpers are intentionally side-effect free. Callers must resolve and
validate immediately before connecting and repeat validation after redirects
or any DNS refresh, preventing DNS rebinding from bypassing the policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
from urllib.parse import urljoin, urlparse


class NetworkPolicyError(ValueError):
    """Raised when an outbound destination violates the safe default policy."""


@dataclass(frozen=True)
class ResourceLimits:
    timeout_seconds: float = 5.0
    max_response_bytes: int = 2 * 1024 * 1024
    max_redirects: int = 3
    max_decompressed_bytes: int = 4 * 1024 * 1024

    def validate(self) -> "ResourceLimits":
        if not 0.1 <= self.timeout_seconds <= 60:
            raise NetworkPolicyError("timeout outside safe bounds")
        if not 1024 <= self.max_response_bytes <= 64 * 1024 * 1024:
            raise NetworkPolicyError("response limit outside safe bounds")
        if not 0 <= self.max_redirects <= 10:
            raise NetworkPolicyError("redirect limit outside safe bounds")
        if not 1024 <= self.max_decompressed_bytes <= 128 * 1024 * 1024:
            raise NetworkPolicyError("decompression limit outside safe bounds")
        return self


def _safe_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError as exc:
        raise NetworkPolicyError(f"invalid IP address: {value!r}") from exc
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        raise NetworkPolicyError(f"non-public destination blocked: {ip}")
    return ip


def validate_resolved_addresses(addresses: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Reject any hostname resolution containing a non-public address."""
    if not addresses:
        raise NetworkPolicyError("hostname resolved to no addresses")
    return tuple(str(_safe_ip(addr)) for addr in addresses)


def resolve_public_host(host: str, port: int) -> tuple[str, ...]:
    """Resolve a host and fail closed if any returned address is unsafe."""
    if not host or not 1 <= int(port) <= 65535:
        raise NetworkPolicyError("invalid destination")
    try:
        infos = socket.getaddrinfo(host, int(port), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise NetworkPolicyError("destination resolution failed") from exc
    addresses = list(dict.fromkeys(info[4][0] for info in infos if info[4]))
    return validate_resolved_addresses(addresses)


def validate_url(url: str, *, allowed_schemes: tuple[str, ...] = ("http", "https")) -> tuple[str, int]:
    """Validate scheme/host and return normalized host + port for pre-connect DNS checks."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in allowed_schemes or parsed.username or parsed.password:
        raise NetworkPolicyError("URL scheme or credentials are not allowed")
    if not parsed.hostname:
        raise NetworkPolicyError("URL has no hostname")
    port = parsed.port or (443 if scheme == "https" else 80)
    if not 1 <= port <= 65535:
        raise NetworkPolicyError("invalid URL port")
    host = parsed.hostname
    try:
        _safe_ip(host)
    except NetworkPolicyError:
        if _is_literal_ip(host):
            raise
    return host, port


def _is_literal_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def validate_redirect(previous_url: str, location: str, *, redirect_count: int, limits: ResourceLimits) -> str:
    """Resolve one redirect and enforce the same policy on every hop."""
    limits.validate()
    if redirect_count >= limits.max_redirects:
        raise NetworkPolicyError("redirect limit exceeded")
    target = urljoin(previous_url, location)
    host, port = validate_url(target)
    resolve_public_host(host, port)
    return target


def enforce_response_size(current_bytes: int, incoming_bytes: int, limits: ResourceLimits) -> int:
    """Bound bytes consumed from a response/decompression stream."""
    limits.validate()
    if incoming_bytes < 0 or current_bytes < 0:
        raise NetworkPolicyError("negative byte count")
    total = current_bytes + incoming_bytes
    if total > limits.max_response_bytes:
        raise NetworkPolicyError("response size limit exceeded")
    return total
