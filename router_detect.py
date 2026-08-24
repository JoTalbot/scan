#!/usr/bin/env python3
"""
Router Detection Engine
========================
Detects router / firewall / access-point / router-firmware devices from HTTP
scan artifacts (server_header, <title>, WWW-Authenticate realm, banner body).

Design rules:
  * Specific vendor signatures BEFORE generic ones.
  * server_header is the strongest signal, then realm (WWW-Authenticate),
    then <title>, then highly-specific phrases in the banner body.
  * Banner body must NOT contain broad vendor words (e.g. "huawei") because
    hosting/CDN footers (CloudFront, LiteSpeed...) pollute it — only very
    specific device phrases are matched there.
  * Known non-router traps: "hws" (Hostinger), "Cisco Umbrella" (DNS service),
    CloudFront/LiteSpeed/Akamai headers, "Ningtron".

API:
    detect_router(server_header=None, title=None, banner=None)
        -> dict | None
        dict keys: vendor, model, device_type, confidence, matched_on
"""

import re

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
DEVICE_ROUTER   = "router"
DEVICE_FIREWALL = "firewall"
DEVICE_AP       = "access_point"

CONF_HIGH   = "high"
CONF_MEDIUM = "medium"

# ----------------------------------------------------------------------------
# Signature tables: (vendor, device_type, confidence, regex, model_regex)
# model_regex is applied to the SAME field that matched.
# ----------------------------------------------------------------------------

SERVER_RULES = [
    # --- Vendor-specific, high confidence ---
    ("MikroTik",    DEVICE_ROUTER,   CONF_HIGH,   r"routeros|mikrotik",                    r"(?i)routeros v?([\d\.]+)"),
    ("TP-Link",     DEVICE_ROUTER,   CONF_HIGH,   r"router webserver|tp[- ]?link|tplink", None),
    ("D-Link",      DEVICE_ROUTER,   CONF_HIGH,   r"d[- ]?link|dlink",                    None),
    ("NETGEAR",     DEVICE_ROUTER,   CONF_HIGH,   r"netgear",                             None),
    ("Zyxel",       DEVICE_ROUTER,   CONF_HIGH,   r"zyxel|zy[xX]el",                      None),
    ("LANCOM",      DEVICE_ROUTER,   CONF_HIGH,   r"lancom",                              None),
    ("Keenetic",    DEVICE_ROUTER,   CONF_HIGH,   r"keenetic",                            None),
    ("ASUS",        DEVICE_ROUTER,   CONF_HIGH,   r"\basus\b",                            r"(?i)(rt-[a-z0-9]+|zenwifi[a-z0-9\-]*)"),
    ("Tenda",       DEVICE_ROUTER,   CONF_HIGH,   r"tenda",                              None),
    ("Sagemcom",    DEVICE_ROUTER,   CONF_HIGH,   r"sagemcom",                           None),
    ("Technicolor", DEVICE_ROUTER,   CONF_HIGH,   r"technicolor|thomson",                None),
    ("SerComm",     DEVICE_ROUTER,   CONF_HIGH,   r"sercomm",                            None),
    ("Mercusys",    DEVICE_ROUTER,   CONF_HIGH,   r"mercusys",                           None),
    ("Arris",       DEVICE_ROUTER,   CONF_HIGH,   r"arris",                              None),
    ("Comtrend",    DEVICE_ROUTER,   CONF_HIGH,   r"comtrend",                           None),
    ("Hitron",      DEVICE_ROUTER,   CONF_HIGH,   r"hitron",                             None),
    ("ipTIME",      DEVICE_ROUTER,   CONF_HIGH,   r"iptime",                             None),
    ("Netis",       DEVICE_ROUTER,   CONF_HIGH,   r"netis|netcore",                      None),
    ("Totolink",    DEVICE_ROUTER,   CONF_HIGH,   r"totolink",                           None),
    ("Ruijie",      DEVICE_ROUTER,   CONF_HIGH,   r"ruijie",                             None),
    ("Huawei",      DEVICE_ROUTER,   CONF_HIGH,   r"huawei ?home ?gateway|huaweihomegateway|echo ?life", None),
    ("Ubiquiti",    DEVICE_ROUTER,   CONF_HIGH,   r"ubiquiti|unifi|edgeos|airos|airmax", None),
    ("Cisco",       DEVICE_ROUTER,   CONF_HIGH,   r"cisco[- ]?(ios|i[eE]os|isr|asr|nexus|sg)|ios[- ]?xe", None),
    # --- Firewalls ---
    ("SonicWALL",   DEVICE_FIREWALL, CONF_HIGH,   r"sonicwall",                          None),
    ("Fortinet",    DEVICE_FIREWALL, CONF_HIGH,   r"fortios|fortigate|fortinet",         None),
    ("Palo Alto",   DEVICE_FIREWALL, CONF_HIGH,   r"palo ?alto|globalprotect|pan-os",    None),
    ("pfSense",     DEVICE_FIREWALL, CONF_HIGH,   r"pfsense",                            None),
    ("OPNsense",    DEVICE_FIREWALL, CONF_HIGH,   r"opnsense",                           None),
    ("Sophos",      DEVICE_FIREWALL, CONF_HIGH,   r"sophos",                             None),
    ("Check Point", DEVICE_FIREWALL, CONF_HIGH,   r"check ?point|smartdefense",          None),
    # --- Generic embedded webservers used by routers (medium) ---
    ("GoAhead",     DEVICE_ROUTER,   CONF_MEDIUM, r"goahead",                            None),
    ("miniupnpd",   DEVICE_ROUTER,   CONF_MEDIUM, r"miniupnpd",                          None),
    ("micro_httpd", DEVICE_ROUTER,   CONF_MEDIUM, r"micro_httpd",                        None),
    ("httpd",       DEVICE_ROUTER,   CONF_MEDIUM, r"^httpd(/\d[\d\.]*)?$",              None),
]

TITLE_RULES = [
    ("MikroTik",    DEVICE_ROUTER,   CONF_HIGH, r"routeros",                              None),
    ("Keenetic",    DEVICE_ROUTER,   CONF_HIGH, r"keenetic",                              None),
    ("Zyxel",       DEVICE_ROUTER,   CONF_HIGH, r"web-based configurator|welcome to zyxel|zy[xX]el",
                                                              r"(?i)zy[xX]el\s+([a-z0-9][a-z0-9\-\.]{2,20})"),
    ("TP-Link",     DEVICE_ROUTER,   CONF_HIGH, r"tp[- ]?link|tplink",
                                                              r"(?i)(tl-wr[a-z0-9]+|wr[a-z0-9]{3,}|archer[a-z0-9\- ]{2,15}|deco[a-z0-9\- ]{2,15})"),
    ("D-Link",      DEVICE_ROUTER,   CONF_HIGH, r"d[- ]?link|dlink",
                                                              r"(?i)(dir-[a-z0-9\-]+|dsl-[a-z0-9\-]+|covr[a-z0-9\-]+)"),
    ("NETGEAR",     DEVICE_ROUTER,   CONF_HIGH, r"netgear",
                                                              r"(?i)(r[0-9]{4}|wndr[0-9a-z]+|nighthawk[a-z0-9\- ]*)"),
    ("Ubiquiti",    DEVICE_ROUTER,   CONF_HIGH, r"unifi|ubiquiti|airmax|edgeos",          None),
    ("ASUS",        DEVICE_ROUTER,   CONF_HIGH, r"asus",
                                                              r"(?i)(rt-[a-z0-9]+|zenwifi[a-z0-9\-]*)"),
    ("Huawei",      DEVICE_ROUTER,   CONF_HIGH, r"huawei|echo ?life|home gateway",        None),
    ("OpenWrt",     DEVICE_ROUTER,   CONF_HIGH, r"\bopenwrt\b|\bluci\b",                          None),
    ("DD-WRT",      DEVICE_ROUTER,   CONF_HIGH, r"dd-wrt|ddwrt",                          None),
    ("Tomato",      DEVICE_ROUTER,   CONF_HIGH, r"\btomato\b",                            None),
    ("Fortinet",    DEVICE_FIREWALL, CONF_HIGH, r"fortigate|fortios",                     None),
    ("pfSense",     DEVICE_FIREWALL, CONF_HIGH, r"pfsense",                               None),
    ("SonicWALL",   DEVICE_FIREWALL, CONF_HIGH, r"sonicwall",                             None),
    ("Sagemcom",    DEVICE_ROUTER,   CONF_HIGH, r"sagemcom",                              None),
    ("Technicolor", DEVICE_ROUTER,   CONF_HIGH, r"technicolor",                           None),
    ("TP-Link",     DEVICE_ROUTER,   CONF_HIGH, r"wireless (n )?(lite )?router",
                                                              r"(?i)(tl-wr[a-z0-9]+|wr[a-z0-9]{3,})"),
]

REALM_RULES = [
    ("TP-Link",      DEVICE_ROUTER,   CONF_HIGH, r"tp[- ]?link|tplink",
                                                              r"(?i)(tl-wr[a-z0-9]+|wr[a-z0-9]{3,}|archer[^\" ]*|deco[^\" ]*)"),
    ("Zyxel",        DEVICE_ROUTER,   CONF_HIGH, r"zyxel|zy[xX]el",
                                                              r"(?i)(p-[a-z0-9\-]+|nbg[a-z0-9\-]+|vm[a-z0-9\-]+|emg[a-z0-9\-]+)"),
    ("D-Link",       DEVICE_ROUTER,   CONF_HIGH, r"d[- ]?link|dlink",
                                                              r"(?i)(dir-[a-z0-9\-]+|dsl-[a-z0-9\-]+)"),
    ("NETGEAR",      DEVICE_ROUTER,   CONF_HIGH, r"netgear", None),
    ("ASUS",         DEVICE_ROUTER,   CONF_HIGH, r"asus",      r"(?i)(rt-[a-z0-9]+)"),
    ("Huawei",       DEVICE_ROUTER,   CONF_HIGH, r"huawei",    r"(?i)(hg[0-9]+[a-z\-]*)"),
    ("MikroTik",     DEVICE_ROUTER,   CONF_HIGH, r"mikrotik|routeros", None),
    ("Generic DSL Router", DEVICE_ROUTER, CONF_HIGH, r"broadband router", None),
    ("Generic Router",     DEVICE_ROUTER, CONF_MEDIUM, r"wireless (n )?(lite )?router", None),
]

# Banner-body rules: ONLY highly specific device phrases (no bare vendor words)
BANNER_RULES = [
    ("MikroTik", DEVICE_ROUTER,   CONF_HIGH, r"routeros router configuration page|mikrotik", None),
    ("Zyxel",    DEVICE_ROUTER,   CONF_HIGH, r"web-based configurator|welcome to zyxel",     None),
    ("TP-Link",  DEVICE_ROUTER,   CONF_HIGH, r"tp[- ]?link", None),
    ("Keenetic", DEVICE_ROUTER,   CONF_HIGH, r"keenetic",    None),
    ("OpenWrt",  DEVICE_ROUTER,   CONF_HIGH, r"\bopenwrt\b|\bluci\b", None),
    ("DD-WRT",   DEVICE_ROUTER,   CONF_HIGH, r"dd-wrt",      None),
    ("Ubiquiti", DEVICE_ROUTER,   CONF_HIGH, r"ubiquiti|unifi", None),
]

_REALM_RE = re.compile(r'(?i)realm="([^"]+)"')


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
        return {
            "vendor": vendor,
            "model": model,
            "device_type": dtype,
            "confidence": conf,
            "matched_on": source,
        }
    return None


def detect_router(server_header=None, title=None, banner=None):
    """Return router descriptor dict or None.

    Priority: server_header -> WWW-Authenticate realm -> <title> -> banner body.
    A generic/medium server-header match (e.g. micro_httpd) is kept as a
    fallback while more specific realm/title signatures are still checked.
    """
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


if __name__ == "__main__":
    # Quick self-test
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
