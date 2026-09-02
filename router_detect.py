#!/usr/bin/env python3
"""Router Detection Engine.

Detects router / firewall / access-point / router-firmware devices from HTTP
artifacts. Detection remains backward-compatible while exposing a deterministic
multi-signal score; no additional network activity is performed here.
"""

import re

DEVICE_ROUTER = "router"
DEVICE_FIREWALL = "firewall"
DEVICE_AP = "access_point"
CONF_HIGH = "high"
CONF_MEDIUM = "medium"
CONF_LOW = "low"

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
    re.compile(r"(?i)\bhws\b"), re.compile(r"(?i)cisco\s+umbrella"),
    re.compile(r"(?i)\bcloudfront\b"), re.compile(r"(?i)\blitespeed\b"),
    re.compile(r"(?i)\bakamai\b"), re.compile(r"(?i)\bningtron\b"),
)


def _match(rules, text, source):
    for vendor, dtype, conf, pattern, model_rx in rules:
        if not re.search(pattern, text, re.IGNORECASE):
            continue
        model = None
        if model_rx:
            mm = re.search(model_rx, text, re.IGNORECASE)
            if mm:
                model = mm.group(1).strip()
        return {"vendor": vendor, "model": model, "device_type": dtype,
                "confidence": conf, "matched_on": source}
    return None


def _legacy_detect(server_header=None, title=None, banner=None):
    """Original priority/fallback semantics retained for compatibility."""
    fallback = None
    if server_header:
        res = _match(SERVER_RULES, server_header, "server_header")
        if res:
            if res["confidence"] == CONF_HIGH:
                return res
            fallback = res
    if banner:
        m = _REALM_RE.search(banner)
        if m:
            res = _match(REALM_RULES, m.group(1), "realm")
            if res:
                return res
    if title:
        res = _match(TITLE_RULES, title, "title")
        if res:
            return res
    if banner:
        res = _match(BANNER_RULES, banner, "banner")
        if res:
            return res
    return fallback


def _score(result, matches, traps):
    """Deterministic evidence score for the selected vendor.

    A strong legacy match starts high enough to preserve existing semantics.
    Independent fields add evidence, while known service/CDN traps reduce weak
    classifications. The score is informational and does not trigger probes.
    """
    base = {CONF_HIGH: 0.80, CONF_MEDIUM: 0.45, CONF_LOW: 0.20}[result["confidence"]]
    weights = {"server_header": 0.55, "realm": 0.25, "title": 0.20, "banner": 0.15}
    sources = {m["matched_on"] for m in matches if m["vendor"] == result["vendor"]}
    score = base
    for source in sources:
        if source != result["matched_on"]:
            score += min(weights[source] * 0.35, 0.10)
    if len(sources) >= 2:
        score += 0.05
    if result.get("model"):
        score += 0.05
    if traps:
        score -= 0.30 if result["confidence"] == CONF_MEDIUM else 0.10
    return round(max(0.0, min(0.99, score)), 3)


def detect_router_scored(server_header=None, title=None, banner=None):
    """Detect using existing signatures and expose multi-signal evidence."""
    result = _legacy_detect(server_header, title, banner)
    if not result:
        return None
    realm = _REALM_RE.search(banner or "")
    fields = (
        ("server_header", server_header or "", SERVER_RULES),
        ("realm", realm.group(1) if realm else "", REALM_RULES),
        ("title", title or "", TITLE_RULES),
        ("banner", banner or "", BANNER_RULES),
    )
    matches = []
    for source, text, rules in fields:
        if text:
            m = _match(rules, text, source)
            if m:
                matches.append(m)
    traps = [source for source, text, _ in fields if any(rx.search(text) for rx in _TRAPS)]
    score = _score(result, matches, traps)
    out = dict(result)
    out["score"] = score
    out["score_confidence"] = CONF_HIGH if score >= 0.75 else CONF_MEDIUM if score >= 0.45 else CONF_LOW
    out["matched_on"] = list(dict.fromkeys(m["matched_on"] for m in matches if m["vendor"] == result["vendor"])) or result["matched_on"]
    out["signals"] = [
        {"source": m["matched_on"], "vendor": m["vendor"], "model": m["model"]}
        for m in matches
    ]
    return out


def detect_router(server_header=None, title=None, banner=None):
    """Backward-compatible descriptor with additional score/evidence fields."""
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
