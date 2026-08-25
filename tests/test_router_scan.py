#!/usr/bin/env python3
"""
pytest-тесты для RouterScan проекта.
Запуск: cd /root/scan && .venv/bin/pytest tests/ -v
(или python3 -m pytest, если pytest установлен)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest  # noqa

from router_detect import detect_router  # noqa


class TestRouterDetect:
    """Тесты детектора роутеров (сигнатуры)."""

    def test_mikrotik_title(self):
        d = detect_router(None, "RouterOS router configuration page", "")
        assert d and d["vendor"] == "MikroTik" and d["confidence"] == "high"

    def test_tplink_server_header(self):
        d = detect_router("Router Webserver", "Login Incorrect",
                          'WWW-Authenticate: Basic realm="TP-LINK Wireless Lite N Router WR741ND"')
        assert d and d["vendor"] == "TP-Link"

    def test_zyxel_model_extraction(self):
        d = detect_router("micro_httpd", ".::Welcome to ZyXEL P-660HN-51::.", "")
        assert d and d["vendor"] == "Zyxel" and d["model"] == "P-660HN-51"

    def test_keenetic_title(self):
        d = detect_router("Web server", "Keenetic Web", "")
        assert d and d["vendor"] == "Keenetic"

    def test_sonicwall_firewall(self):
        d = detect_router("SonicWALL", "Document Moved", "")
        assert d and d["device_type"] == "firewall"

    def test_lancom(self):
        d = detect_router("LANCOM", "LANCOM: Error - Access Forbidden", "")
        assert d and d["vendor"] == "LANCOM"

    def test_negative_hostinger(self):
        """hws = Hostinger — НЕ роутер."""
        assert detect_router("hws", "409 Conflict", "platform: hostinger") is None

    def test_negative_cloudfront(self):
        assert detect_router("CloudFront", "ERROR: The request could not be satisfied", "") is None

    def test_negative_cisco_umbrella(self):
        assert detect_router("Cisco Umbrella", "", "") is None

    def test_negative_nginx(self):
        assert detect_router("nginx", "Welcome to nginx!", "") is None

    def test_negative_lucide_false_positive(self):
        """openwrt/luci не должен матчить 'lucide' (JS-библиотека)."""
        assert detect_router("nginx", "MASTER CASH", 'src="https://unpkg.com/lucide@0.468.0"') is None

    def test_openwrt_word_boundary(self):
        d = detect_router(None, None, "URL=cgi-bin/luci/")
        assert d and d["vendor"] == "OpenWrt"

    def test_pfsense(self):
        d = detect_router(None, "pfSense", "")
        assert d and d["vendor"] == "pfSense"


class TestCreds:
    """Тесты списков паролей."""

    def test_creds_for_fast_small(self):
        from router_auth_check import creds_for_fast, load_extra_creds
        c = creds_for_fast("MikroTik", {})
        assert len(c) < 56  # fast-режим компактнее полного
        assert ("admin", "") in c  # заводская пара MikroTik на месте

    def test_creds_full_larger(self):
        from router_auth_check import creds_for, creds_for_fast
        full = creds_for("MikroTik", {})
        fast = creds_for_fast("MikroTik", {})
        assert len(full) > len(fast)

    def test_no_duplicates(self):
        from router_auth_check import creds_for
        c = creds_for("Zyxel", {})
        keys = [(u.lower(), p.lower()) for u, p in c]
        assert len(keys) == len(set(keys))


class TestSnmp:
    """Тесты raw SNMP-парсера."""

    def test_snmp_oid_bytes(self):
        from port_probe import snmp_oid_bytes
        # 1.3.6.1 -> 0x2b 0x06 0x01
        assert snmp_oid_bytes("1.3.6.1") == bytes([0x2B, 0x06, 0x01])

    def test_snmp_build_get_structure(self):
        from port_probe import snmp_build_get
        pkt = snmp_build_get("public", "1.3.6.1.2.1.1.1.0")
        # SEQUENCE(0x30) + version(0x02 0x01 0x01) + community "public"
        assert pkt[0] == 0x30
        assert b"public" in pkt
        assert pkt[2:5] == bytes([0x02, 0x01, 0x01])  # version 1

    def test_snmp_parse_value_octet(self):
        from port_probe import snmp_parse_value
        # минимальный ответ: ... OID TLV + OCTET STRING "test"
        from port_probe import snmp_tlv, snmp_oid_bytes
        oid = snmp_oid_bytes("1.3.6.1.2.1.1.1.0")
        data = snmp_tlv(0x30, snmp_tlv(0x06, oid) + snmp_tlv(0x04, b"test-value"))
        assert snmp_parse_value(data) == "test-value"


class TestApiEncoder:
    """Тесты кодировщика MikroTik API."""

    def test_encode_short_word(self):
        from router_auth_check import _api_encode_word
        assert _api_encode_word("hi") == b"\x02hi"

    def test_encode_sentence_terminator(self):
        from router_auth_check import _api_encode_sentence
        s = _api_encode_sentence(["/login", "name=admin"])
        assert s.endswith(b"\x00")
