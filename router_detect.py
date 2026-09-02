#!/usr/bin/env python3
"""
Router Detection Engine
========================
Detects router / firewall / access-point / router-firmware devices from HTTP
scan artifacts without performing additional network activity.

Detection is multi-signal: independent server-header, WWW-Authenticate realm,
title and banner evidence is combined into a deterministic confidence score.
"""

import re

DEVICE_ROUTER   = "router"
DEVICE_FIREWALL = "firewall"
DEVICE_AP       = "access_point"

CONF_HIGH   = "high"
CONF_MEDIUM = "medium"
CONF_LOW    = "low"

SERVER_RULES = [
    ("MikroTik", DEVICE_ROUTER, CONF_HIGH, r"routeros|mikrotik", r"(?i)routeros v?([\d\.]+)"),
    ("TP-Link", DEVICE_ROUTER, CONF_HIGH, r"router webserver|tp[- ]?link|tplink", None),
    ("D-Link", DEVICE_ROUTER, CONF_HIGH, r"d[- ]?link|dlink", None),
    ("NETGEAR", DEVICE_ROUTER, CONF_HIGH, r"netgear", None),
    ("Zyxel", DEVICE_ROUTER, CONF_HIGH, r"zyxel|zy[xX]el", None),
    ("LANCOM", DEVICE_ROUTER, CONF_HIGH, r"lancom", None),
    ("Keenetic", DEVICE_ROUTER, CONF_HIGH, r"keenetic", None),
    ("ASUS", DEVICE_ROUTER, CONF_HIGH, r"\basus\b", r"(?i)(rt-[a-z0-9]+|zenwifi[a-z0-9\-]*)"),
    ("Tenda", DEVICE_ROUTER, CONF_HIGH, r"tenda", None),
    ("Sagemcom", DEVICE_ROUTER, CONF_HIGH, r"sagemcom", None),
    ("Technicolor", DEVICE_ROUTER, CONF_HIGH, r"technicolor|thomson", None),
    ("SerComm", DEVICE_ROUTER, CONF_HIGH, r"sercomm", None),
    ("Mercusys", DEVICE_ROUTER, CONF_HIGH, r"mercusys", None),
    ("Arris", DEVICE_ROUTER, CONF_HIGH, r"arris", None),
    ("Comtrend", DEVICE_ROUTER, CONF_HIGH, r"comtrend", None),
    ("Hitron", DEVICE_ROUTER, CONF_HIGH, r"hitron", None),
    ("ipTIME", DEVICE_ROUTER, CONF_HIGH, r"iptime", None),
    ("Netis", DEVICE_ROUTER, CONF_HIGH, r"netis|netcore", None),
    ("Totolink", DEVICE_ROUTER, CONF_HIGH, r"totolink", None),
    ("Ruijie", DEVICE_ROUTER, CONF_HIGH, r"ruijie", None),
    ("Huawei", DEVICE_ROUTER, CONF_HIGH, r"huawei ?home ?gateway|huaweihomegateway|echo ?life", None),
    ("Ubiquiti", DEVICE_ROUTER, CONF_HIGH, r"ubiquiti|unifi|edgeos|airos|airmax", None),
    ("Cisco", DEVICE_ROUTER, CONF_HIGH, r"cisco[- ]?(ios|i[eE]os|isr|asr|nexus|sg)|ios[- ]?xe", None),
    ("SonicWALL", DEVICE_FIREWALL, CONF_HIGH, r"sonicwall", None),
    ("Fortinet", DEVICE_FIREWALL, CONF_HIGH, r"fortios|fortigate|fortinet", None),
    ("Palo Alto", DEVICE_FIREWALL, CONF_HIGH, r"palo ?alto|globalprotect|pan-os", None),
    ("pfSense", DEVICE_FIREWALL, CONF_HIGH, r"pfsense", None),
    ("OPNsense", DEVICE_FIREWALL, CONF_HIGH, r"opnsense", None),
    ("Sophos", DEVICE_FIREWALL, CONF_HIGH, r"sophos", None),
    ("Check Point", DEVICE_FIREWALL, CONF_HIGH, r"check ?point|smartdefense", None),
    ("GoAhead", DEVICE_ROUTER, CONF_MEDIUM, r"goahead", None),
    ("miniupnpd", DEVICE_ROUTER, CONF_MEDIUM, r"miniupnpd", None),
    ("micro_httpd", DEVICE_ROUTER, CONF_MEDIUM, r"micro_httpd", None),
    ("httpd", DEVICE_ROUTER, CONF_MEDIUM, r"^httpd(/\d[\d\.]*)?$", None),
]

TITLE_RULES = [
    ("MikroTik", DEVICE_ROUTER, CONF_HIGH, r"routeros", None),
    ("Keenetic", DEVICE_ROUTER, CONF_HIGH, r"keenetic", None),
    ("Zyxel", DEVICE_ROUTER, CONF_HIGH, r"web-based configurator|welcome to zyxel|zy[xX]el", r"(?i)zy[xX]el\s+([a-z0-9][a-z0-9\-\.]{2,20})"),
    ("TP-Link", DEVICE_ROUTER, CONF_HIGH, r"tp[- ]?link|tplink", r"(?i)(tl-wr[a-z0-9]+|wr[a-z0-9]{3,}|archer[a-z0-9\- ]{2,15}|deco[a-z0-9\- ]{2,15})"),
    ("D-Link", DEVICE_ROUTER, CONF_HIGH, r"d[- ]?link|dlink", r"(?i)(dir-[a-z0-9\-]+|dsl-[a-z0-9\-]+|covr[a-z0-9\-]+)"),
    ("NETGEAR", DEVICE_ROUTER, CONF_HIGH, r"netgear", r"(?i)(r[0-9]{4}|wndr[0-9a-z]+|nighthawk[a-z0-9\- ]*)"),
    ("Ubiquiti", DEVICE_ROUTER, CONF_HIGH, r"unifi|ubiquiti|airmax|edgeos", None),
    ("ASUS", DEVICE_ROUTER, CONF_HIGH, r"asus", r"(?i)(rt-[a-z0-9]+|zenwifi[a-z0-9\-]*)"),
    ("Huawei", DEVICE_ROUTER, CONF_HIGH, r"huawei|echo ?life|home gateway", None),
    ("OpenWrt", DEVICE_ROUTER, CONF_HIGH, r"\bopenwrt\b|\bluci\b", None),
    ("DD-WRT", DEVICE_ROUTER, CONF_HIGH, r"dd-wrt|ddwrt", None),
    ("Tomato", DEVICE_ROUTER, CONF_HIGH, r"\btomato\b", None),
    ("Fortinet", DEVICE_FIREWALL, CONF_HIGH, r"fortigate|fortios", None),
    ("pfSense", DEVICE_FIREWALL, CONF_HIGH, r"pfsense", None),
    ("SonicWALL", DEVICE_FIREWALL, CONF_HIGH, r"sonicwall", None),
    ("Sagemcom", DEVICE_ROUTER, CONF_HIGH, r"sagemcom", None),
    ("Technicolor", DEVICE_ROUTER, CONF_HIGH, r"technicolor", None),
    ("Hikvision", DEVICE_ROUTER, CONF_HIGH, r"hikvision", None),
    ("TP-Link", DEVICE_ROUTER, CONF_HIGH, r"wireless (n )?(lite )?router", r"(?i)(tl-wr[a-z0-9]+|wr[a-z0-9]{3,})"),
]

REALM_RULES = [
    ("TP-Link", DEVICE_ROUTER, CONF_HIGH, r"tp[- ]?link|tplink", r"(?i)(tl-wr[a-z0-9]+|wr[a-z0-9]{3,}|archer[^\" ]*|deco[^\" ]*)"),
    ("Zyxel", DEVICE_ROUTER, CONF_HIGH, r"zyxel|zy[xX]el", r"(?i)(p-[a-z0-9\-]+|nbg[a-z0-9\-]+|vm[a-z0-9\-]+|emg[a-z0-9\-]+)"),
    ("D-Link", DEVICE_ROUTER, CONF_HIGH, r"d[- ]?link|dlink", r"(?i)(dir-[a-z0-9\-]+|dsl-[a-z0-9\-]+)"),
    ("NETGEAR", DEVICE_ROUTER, CONF_HIGH, r"netgear", None),
    ("ASUS", DEVICE_ROUTER, CONF_HIGH, r"asus", r"(?i)(rt-[a-z0-9]+)"),
    ("Huawei", DEVICE_ROUTER, CONF_HIGH, r"huawei", r"(?i)(hg[0-9]+[a-z\-]*)"),
    ("MikroTik", DEVICE_ROUTER, CONF_HIGH, r"mikrotik|routeros", None),
    ("Generic DSL Router", DEVICE_ROUTER, CONF_HIGH, r"broadband router", None),
    ("Generic Router", DEVICE_ROUTER, CONF_MEDIUM, r"wireless (n )?(lite )?router", None),
]

BANNER_RULES = [
    ("MikroTik", DEVICE_ROUTER, CONF_HIGH, r"routeros router configuration page|mikrotik", None),
    ("Zyxel", DEVICE_ROUTER, CONF_HIGH, r"web-based configurator|welcome to zyxel", None),
    ("TP-Link", DEVICE_ROUTER, CONF_HIGH, r"tp[- ]?link", None),
    ("Keenetic", DEVICE_ROUTER, CONF_HIGH, r"keenetic", None),
    ("OpenWrt", DEVICE_ROUTER, CONF_HIGH, r"\bopenwrt\b|\bluci\b", None),
    ("DD-WRT", DEVICE_ROUTER, CONF_HIGH, r"dd-wrt", None),
    ("Ubiquiti", DEVICE_ROUTER, CONF_HIGH, r"ubiquiti|unifi", None),
]

_REALM_RE = re.compile(r'(?i)realm="([^"]+)"')
_TRAPS = (
    re.compile(r"(?i)\bhws\b"),
    re.compile(r"(?i)cisco\s+umbrella"),
    re.compile(r"(?i)\bcloudfront\b"),
    re.compile(r"(?i)\blitespeed\b"),
    re.compile(r"(?i)\bakamai\b"),
    re.compile(r"(?i)\bningtron\b"),
)


def _match(rules, text, source):
    for vendor, dtype, conf, pattern, model_rx in rules:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        model = None
        if model_rx:
            mm = re.search(model_rx, text, re.IGNORECASE)
            if mm:
                model = mm.group(1).strip()
        return {"vendor": vendor, "model": model, "device_type": dtype,
                "confidence": conf, "matched_on": source}
    return None


def _specificity(result):
    if not result:
        return 0.0
    if result["vendor"] in {"Generic Router", "GoAhead", "miniupnpd", "micro_httpd", "httpd"}:
        return 0.35
    if result["vendor"] in {"Generic DSL Router"}:
        return 0.55
    return 1.0


def _confidence_category(score):
    if score >= 0.75:
        return CONF_HIGH
    if score >= 0.45:
        return CONF_MEDIUM
    if score >= 0.25:
        return CONF_LOW
    return None


def detect_router_scored(server_header=None, title=None, banner=None):
    """Return a multi-signal detection result with deterministic score.

    This function only evaluates already-collected HTTP artifacts. It never
    performs active probing. Independent fields contribute evidence; agreeing
    vendor signals receive a bonus, while known non-router traps suppress
    otherwise weak/generic matches.
    """
    fields = {
        "server_header": server_header or "",
        "title": title or "",
    }
    realm = None
    if banner:
        m = _REALM_RE.search(banner)
        if m:
            realm = m.group(1)
    fields["realm"] = realm or ""
    fields["banner"] = banner or ""

    results = []
    for source, text, rules in (
        ("server_header", fields["server_header"], SERVER_RULES),
        ("realm", fields["realm"], REALM_RULES),
        ("title", fields["title"], TITLE_RULES),
        ("banner", fields["banner"], BANNER_RULES),
    ):
        if text:
            result = _match(rules, text, source)
            if result:
                results.append(result)

    if not results:
        return None

    traps = [source for source, text in fields.items() if any(rx.search(text) for rx in _TRAPS)]
    # Field weights intentionally cap the contribution of banner-only evidence.
    weights = {"server_header": 0.55, "realm": 0.25, "title": 0.15, "banner": 0.10}
    by_vendor = {}
    for result in results:
        by_vendor.setdefault(result["vendor"], []).append(result)

    # Prefer the strongest vendor evidence, then independent agreement.
    vendor, vendor_results = max(
        by_vendor.items(), key=lambda item: (
            sum(weights[r["matched_on"]] * _specificity(r) for r in item[1]),
            len({r["matched_on"] for r in item[1]}),
        )
    )
    sources = list(dict.fromkeys(r["matched_on"] for r in vendor_results))
    score = sum(weights[s] * _specificity(r) for s in sources for r in vendor_results if r["matched_on"] == s)
    if len(sources) >= 2:
        score += min(0.15, 0.05 * (len(sources) - 1))
    if any(r["vendor"] == vendor and r["model"] for r in vendor_results):
        score += 0.05
    if traps:
        score -= 0.45
    score = max(0.0, min(0.99, score))

    best = max(vendor_results, key=lambda r: (weights[r["matched_on"]], bool(r["model"])))
    category = _confidence_category(score)
    if category is None:
        return None
    return {
        "vendor": best["vendor"],
        "model": next((r["model"] for r in vendor_results if r["model"]), None),
        "device_type": best["device_type"],
        "confidence": category,
        "score": round(score, 3),
        "matched_on": sources[0] if len(sources) == 1 else sources,
        "signals": [{"source": r["matched_on"], "vendor": r["vendor"], "model": r["model"]} for r in vendor_results],
    }


def detect_router(server_header=None, title=None, banner=None):
    """Backward-compatible descriptor using the multi-signal scorer."""
    return detect_router_scored(server_header, title, banner)


if __name__ == "__main__":
    tests = [
        (None, "RouterOS router configuration page", "HTTP/1.1 200 OK"),
        ("Router Webserver", "Login Incorrect", 'HTTP/1.1 401 N/A\r\nWWW-Authenticate: Basic realm="TP-LINK Wireless Lite N Router WR741ND"'),
        ("Web server", "Keenetic Web", "HTTP/1.1 200 OK"),
        (None, ".::Welcome to the Web-Based Configurator::.", ""),
        ("micro_httpd", ".::Welcome to ZyXEL P-660HN-51::.", ""),
        ("LANCOM", "LANCOM: Error - Access Forbidden", ""),
        ("SonicWALL", "Document Moved", ""),
        ("hws", "409 Conflict", "platform: hostinger"),
        ("CloudFront", "ERROR: The request could not be satisfied", ""),
        ("Cisco Umbrella", "", ""),
        ("nginx", "Welcome to nginx!", ""),
    ]
    for srv, ttl, ban in tests:
        print("%-18s | %-45s | %s" % (srv or "", (ttl or "")[:44], detect_router(srv, ttl, ban)))
