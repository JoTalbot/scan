#!/usr/bin/env python3
"""
Shodan InternetDB Enrichment (№3 из плана)
==========================================
Бесплатное обогащение найденных роутеров данными Shodan InternetDB
(без ключа и лимитов): открытые порты, CVE, CPE, hostnames, tags.

Данные обновляются Shodan еженедельно. Это дополняет наш собственный скан
данными о портах, которые мы не проверяем, и CVE-списками (в т.ч. для
устройств, где версия не видна — InternetDB знает CPE).

Сохранение:
  * scan_routers.internetdb  — JSON (ports, cves, cpes, hostnames, tags)
  * internetdb_report.md     — сводка по CVE

Usage:
    python3 internetdb_enrich.py              # все scan_routers
    python3 internetdb_enrich.py --ip 1.2.3.4 # один IP
    python3 internetdb_enrich.py --limit 50   # первые N
    python3 internetdb_enrich.py --no-db      # не писать в БД (только отчёт)
"""

import os
import sys
import json
import time
import sqlite3
import argparse
import datetime
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(BASE_DIR, "isp_cidr.db"))
UA = "Mozilla/5.0 (RouterScan Project; research)"
API = "https://internetdb.shodan.io/{ip}"


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def internetdb_lookup(ip, timeout=8):
    """GET internetdb.shodan.io/{ip}. Возвращает dict | None."""
    try:
        req = urllib.request.Request(API.format(ip=ip), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ip": ip, "not_found": True}  # IP не в базе InternetDB
        return None
    except Exception:
        return None
    return None


def enrich_all(conn, ips, delay=0.25):
    cur = conn.cursor()
    results = {}
    for i, ip in enumerate(ips):
        data = internetdb_lookup(ip)
        if data:
            results[ip] = data
            # сохраняем JSON в scan_routers
            if "not_found" in data:
                cur.execute("UPDATE scan_routers SET internetdb = ? WHERE ip = ?",
                            (json.dumps({"not_found": True}), ip))
            else:
                cur.execute("UPDATE scan_routers SET internetdb = ? WHERE ip = ?",
                            (json.dumps(data), ip))
        if (i + 1) % 25 == 0 or i + 1 == len(ips):
            print(f"  🔄 [{i+1}/{len(ips)}] обработано, найдено: {sum(1 for v in results.values() if 'not_found' not in v)}")
        time.sleep(delay)  # вежливость к API
    conn.commit()
    return results


def build_report(results, routers_meta):
    """Сводка по CVE из InternetDB."""
    lines = ["# 🌐 InternetDB Enrichment Report\n",
             f"**Сформирован:** {get_now()}\n",
             f"**IP с данными:** {sum(1 for v in results.values() if 'not_found' not in v)} из {len(results)}\n"]
    vuln_rows = []
    for ip, data in results.items():
        if "not_found" in data:
            continue
        cves = data.get("vulns") or data.get("cves") or []
        if not cves:
            continue
        vendor = routers_meta.get(ip, {}).get("vendor", "-")
        for cve in cves:
            vuln_rows.append((ip, vendor, cve, ",".join(str(p) for p in data.get("ports", [])[:5])))
    if vuln_rows:
        lines.append("## 🛡️ CVE по данным InternetDB\n")
        lines.append("| IP | Вендор | CVE | Порты |")
        lines.append("|---|---|---|---|")
        for ip, vendor, cve, ports in sorted(vuln_rows, key=lambda x: x[2]):
            lines.append(f"| {ip} | {vendor} | [{cve}](https://nvd.nist.gov/vuln/detail/{cve}) | {ports} |")
    else:
        lines.append("_CVE не обнаружено._\n")
    # топ открытых портов по InternetDB
    port_counter = {}
    for data in results.values():
        if "not_found" in data:
            continue
        for p in data.get("ports", []):
            port_counter[p] = port_counter.get(p, 0) + 1
    if port_counter:
        lines.append("\n## 🔌 Топ портов (по InternetDB)\n")
        lines.append("| Порт | Устройств |")
        lines.append("|---|---|")
        for p, c in sorted(port_counter.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"| {p} | {c} |")
    lines.append("\n---\n*Данные Shodan InternetDB (обновление еженедельно).*")
    with open(os.path.join(BASE_DIR, "internetdb_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("internetdb_report.md сохранён")
    return len(vuln_rows)


def main():
    parser = argparse.ArgumentParser(description="Shodan InternetDB enrichment")
    parser.add_argument("--ip", help="Один IP")
    parser.add_argument("--limit", type=int, help="Первые N роутеров")
    parser.add_argument("--delay", type=float, default=0.25, help="Пауза между запросами (сек)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(scan_routers)")]
    if "internetdb" not in cols:
        cur.execute("ALTER TABLE scan_routers ADD COLUMN internetdb TEXT")
        conn.commit()

    if args.ip:
        rows = cur.execute("SELECT ip, vendor FROM scan_routers WHERE ip = ?", (args.ip,)).fetchall()
    else:
        sql = "SELECT ip, vendor FROM scan_routers"
        if args.limit:
            sql += " LIMIT ?"
            rows = cur.execute(sql, (args.limit,)).fetchall()
        else:
            rows = cur.execute(sql).fetchall()
    conn.close()

    if not rows:
        print("Нет целей")
        return
    ips = [r[0] for r in rows]
    meta = {r[0]: {"vendor": r[1]} for r in rows}
    print(f"🔍 Обогащаю {len(ips)} роутеров через InternetDB (пауза {args.delay}s)...")

    conn = sqlite3.connect(DB_PATH)
    results = enrich_all(conn, ips, args.delay)
    conn.close()

    n_cve = build_report(results, meta)
    print(f"✅ Готово: данных по {sum(1 for v in results.values() if 'not_found' not in v)} IP, "
          f"устройств с CVE: {n_cve}")


if __name__ == "__main__":
    main()
