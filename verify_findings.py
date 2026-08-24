#!/usr/bin/env python3
"""
Double-check findings (№7)
==========================
Динамические IP меняют содержимое — находка, сделанная однажды, может
исчезнуть. Скрипт перепроверяет пары из router_credentials через заданный
интервал (по умолчанию — всё, что старше 12 часов), и:
  * подтверждает пару (verified_at обновляется) — если она всё ещё работает;
  * помечает пару revoked — если больше не работает (IP переиспользован).

Usage:
    python3 verify_findings.py [--hours 12] [--ip X.X.X.X]
"""
import os
import sys
import asyncio
import sqlite3
import argparse
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(BASE_DIR, "isp_cidr.db"))
sys.path.insert(0, BASE_DIR)
import router_auth_check as rac  # noqa

CHANNEL_FN = {
    "basic": lambda ip, u, p: rac.check_basic(ip, 80, [(u, p)], 6),
    "rest": lambda ip, u, p: rac.check_basic(ip, 80, [(u, p)], 6, path="/rest/ip/address"),
    "mikrotik_api": lambda ip, u, p: rac.check_mikrotik_api(ip, 8728, [(u, p)], 6),
    "zyxel": lambda ip, u, p: rac.check_zyxel(ip, 80, [(u, p)], 6),
    "sonicwall": lambda ip, u, p: rac.check_sonicwall(ip, 80, [(u, p)], 6),
    "luci": lambda ip, u, p: rac.check_luci(ip, 80, [(u, p)], 6),
}


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def verify_one(row):
    ip, port, vendor, user, pwd, method = row
    fn = CHANNEL_FN.get(method)
    if not fn:
        return ip, "skip-unknown-method"
    try:
        found, _, _ = await fn(ip, user, pwd)
    except Exception:
        found = None
    return ip, ("verified" if found else "revoked")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=12.0, help="Мин. возраст пары для проверки")
    parser.add_argument("--ip", help="Проверить только конкретный IP")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cutoff = (datetime.datetime.now(datetime.timezone.utc) -
              datetime.timedelta(hours=args.hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.ip:
        rows = cur.execute("SELECT ip, port, vendor, username, password, auth_method "
                           "FROM router_credentials WHERE ip = ?", (args.ip,)).fetchall()
    else:
        rows = cur.execute("SELECT ip, port, vendor, username, password, auth_method "
                           "FROM router_credentials WHERE checked_at < ?", (cutoff,)).fetchall()
    conn.close()

    if not rows:
        print("Нет пар для перепроверки.")
        return
    print(f"Перепроверяю {len(rows)} пар...")
    results = await asyncio.gather(*[verify_one(r) for r in rows])

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = get_now()
    for ip, status in results:
        if status == "verified":
            cur.execute("UPDATE router_credentials SET checked_at = ? WHERE ip = ?", (now, ip))
            print(f"  ✅ {ip} — подтверждена")
        elif status == "revoked":
            cur.execute("UPDATE router_credentials SET auth_method = auth_method || '+revoked', "
                        "realm = COALESCE(realm || '; ', '') || 'revoked at ' || ? WHERE ip = ?", (now, ip))
            print(f"  ⚠️  {ip} — БОЛЬШЕ НЕ РАБОТАЕТ (revoked)")
    conn.commit()
    conn.close()
    print("Готово.")


if __name__ == "__main__":
    asyncio.run(main())
