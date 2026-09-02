from router_detect import detect_router


def test_strong_server_header_scores_high():
    result = detect_router("RouterOS v7.16", "", "")
    assert result["vendor"] == "MikroTik"
    assert result["confidence"] == "high"
    assert result["score"] >= 0.8
    assert result["matched_on"] == ["server_header"]


def test_independent_realm_and_title_signals_agree():
    banner = 'WWW-Authenticate: Basic realm="TP-Link Wireless Lite N Router WR741ND"'
    result = detect_router("Web server", "TP-Link Wireless Router", banner)
    assert result["vendor"] == "TP-Link"
    assert result["confidence"] == "high"
    assert result["score"] > 0.8
    assert set(result["matched_on"]) >= {"realm", "title"}
    assert len(result["signals"]) >= 2


def test_specific_banner_is_usable_without_active_probe():
    result = detect_router(None, None, "OpenWrt LuCI administration interface")
    assert result["vendor"] == "OpenWrt"
    assert result["confidence"] == "high"
    assert result["matched_on"] == ["banner"]
    assert result["score"] >= 0.8


def test_generic_web_server_does_not_get_high_confidence():
    result = detect_router("httpd", "", "")
    assert result is not None
    assert result["confidence"] == "medium"
    assert result["score"] < 0.75


def test_non_router_trap_suppresses_weak_match():
    result = detect_router("CloudFront", "", "")
    assert result is None


def test_cisco_umbrella_is_not_misclassified_as_router():
    result = detect_router("Cisco Umbrella", "", "")
    assert result is None


def test_model_signal_is_preserved():
    result = detect_router(
        "Web server",
        "Login",
        'WWW-Authenticate: Basic realm="TP-Link Wireless Lite N Router WR741ND"',
    )
    assert result["vendor"] == "TP-Link"
    assert result["model"] == "WR741ND"
    assert "realm" in result["matched_on"]


def test_scoring_is_deterministic():
    args = ("Web server", "Keenetic Web", "HTTP/1.1 200 OK")
    assert detect_router(*args) == detect_router(*args)
