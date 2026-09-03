import pytest

from detection_intelligence import (
    DETECTOR_VERSION,
    VulnerabilityRecord,
    calibrate_confidence,
    differential,
    fingerprint_id,
    normalize_vulnerabilities,
    risk_score,
    risk_tier,
)
from network_policy import (
    NetworkPolicyError,
    ResourceLimits,
    enforce_response_size,
    validate_redirect,
    validate_resolved_addresses,
    validate_url,
)


def test_confidence_calibration_is_bounded_and_deterministic():
    assert calibrate_confidence(0.79, evidence_count=2) == (0.84, "high")
    assert calibrate_confidence(4, evidence_count=99)[0] == 0.99
    assert calibrate_confidence(-1)[0] == 0.0


def test_fingerprint_is_opaque_and_versioned():
    a = fingerprint_id("MikroTik", "RB4011")
    b = fingerprint_id("MikroTik", "RB4011", DETECTOR_VERSION)
    assert a == b
    assert len(a) == 24
    assert "MikroTik" not in a


def test_vulnerability_normalization_deduplicates():
    records = normalize_vulnerabilities([
        VulnerabilityRecord("cve-2024-0001", " Acme ", " Router OS ", "1", 9.8),
        VulnerabilityRecord("CVE-2024-0001", "acme", "router os", "1", 9.8),
    ])
    assert len(records) == 1
    assert records[0].cve_id == "CVE-2024-0001"
    assert records[0].vendor == "acme"


def test_risk_score_prioritizes_kev_and_epSS():
    low = VulnerabilityRecord("CVE-1", "v", "p", cvss=5.0, epss=0.1)
    high = VulnerabilityRecord("CVE-2", "v", "p", cvss=9.8, epss=0.9, kev=True)
    assert risk_score(high) > risk_score(low)
    assert risk_tier(risk_score(high)) == "critical"


def test_differential_statuses():
    assert differential(None, {"fingerprint": "a"}).status == "NEW"
    assert differential({"fingerprint": "a"}, None).status == "RESOLVED"
    assert differential({"fingerprint": "a"}, {"fingerprint": "a"}).status == "UNCHANGED"
    assert differential({"fingerprint": "a"}, {"fingerprint": "b"}).status == "CHANGED"


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1",
    "169.254.1.1", "::1", "fc00::1", "fe80::1", "224.0.0.1",
])
def test_private_reserved_and_special_addresses_are_blocked(address):
    with pytest.raises(NetworkPolicyError):
        validate_resolved_addresses([address])


def test_public_address_is_allowed():
    assert validate_resolved_addresses(["8.8.8.8"]) == ("8.8.8.8",)


def test_url_rejects_embedded_credentials_and_unsafe_literal_ip():
    with pytest.raises(NetworkPolicyError):
        validate_url("http://user:pass@example.com/")
    with pytest.raises(NetworkPolicyError):
        validate_url("http://127.0.0.1/")


def test_redirect_revalidates_destination(monkeypatch):
    monkeypatch.setattr("network_policy.resolve_public_host", lambda host, port: ("8.8.8.8",))
    assert validate_redirect("https://example.com/a", "/b", redirect_count=0, limits=ResourceLimits()) == "https://example.com/b"
    with pytest.raises(NetworkPolicyError):
        validate_redirect("https://example.com/a", "/b", redirect_count=3, limits=ResourceLimits(max_redirects=3))


def test_response_limit_is_bounded():
    limits = ResourceLimits(max_response_bytes=1024)
    assert enforce_response_size(512, 512, limits) == 1024
    with pytest.raises(NetworkPolicyError):
        enforce_response_size(512, 513, limits)
