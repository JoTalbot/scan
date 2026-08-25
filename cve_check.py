#!/usr/bin/env python3
"""
CVE Mapping for detected routers (№5)
======================================
Сопоставляет версии ПО обнаруженных роутеров с известными уязвимостями
(локальная база известных CVE для популярных вендоров).

Версия извлекается из title/banner/server_header роутеров; для каждой
находки выводится список CVE с ссылками. Результаты сохраняются в
scan_routers.cves (JSON) и в REPORT.md секцию "Уязвимые устройства".

Usage:
    python3 cve_check.py              # проверить все scan_routers
    python3 cve_check.py --ip X.X.X.X
    python3 cve_check.py --refresh    # пересчитать cves для всех
"""

import os
import re
import json
import sqlite3
import argparse
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(BASE_DIR, "isp_cidr.db"))

# ---------------------------------------------------------------------------
# Локальная база известных CVE (версия -> список уязвимостей)
# ВНИМАНИЕ: неполная, для демонстрации подхода. Полный список — NVD API.
# ---------------------------------------------------------------------------
CVE_DB = {
    "MikroTik": [
        # (паттерн версии, min, max, CVE, описание)
        (r"RouterOS v?([\d]+\.[\d.]+)", "0", "6.42", "CVE-2018-14847",
         "Winbox arbitrary file read / RCE (patcher exploited 400k+ devices)"),
        (r"RouterOS v?([\d]+\.[\d.]+)", "0", "6.49.6", "CVE-2023-30799",
         "Disk encryption bypass, root access via bootloader"),
        (r"RouterOS v?([\d]+\.[\d.]+)", "0", "6.45.9", "CVE-2020-7383",
         "RCE via Winbox when certain packages installed (CVE-2018-14847 chain)"),
        (r"RouterOS v?([\d]+\.[\d.]+)", "6.41", "6.45.9", "CVE-2021-37848",
         "SMB buffer overflow, unauth RCE"),
    ],
    "pfSense": [
        (r"pfSense[\s/:]*([\d]+\.[\d.]+)", "0", "2.5.2", "CVE-2021-41282",
         "pfblockerng RCE (authed)"),
        (r"pfSense[\s/:]*([\d]+\.[\d.]+)", "0", "2.6.0", "CVE-2023-42326",
         "status_rrd_img.php RCE"),
    ],
    "OPNsense": [
        (r"OPNsense[\s/:]*([\d]+\.[\d.]+)", "0", "22.7.6", "CVE-2022-40018",
         "CSRF -> RCE via vulnerable plugins"),
    ],
    "SonicWALL": [
        (r"SonicWALL[\s/:]*([\d]+\.[\d.]+)", "0", "6.5.4.7", "CVE-2021-20016",
         "SQLi in SSL VPN (CVE-2021-20016, exploited in the wild)"),
        (r"SonicWALL[\s/:]*([\d]+\.[\d.]+)", "0", "7.0.1", "CVE-2022-22274",
         "Stack overflow in SonicOS, unauth RCE"),
    ],
    "Cisco": [
        (r"cisco-IOS[\s/:]*([\d]+\.[\d.]+)", "0", "15.7", "CVE-2018-0171",
         "Smart Install RCE (100% reliable, unauth)"),
    ],
    "D-Link": [
        (r"D-Link[\s/:]*([\d]+\.[\d.]+)", "0", "1.0", "CVE-2021-45382",
         "HNAP RCE in multiple DIR models"),
    ],
    "TP-Link": [
        (r"TP-Link[\s/:]*([\d]+\.[\d.]+)", "0", "1.0", "CVE-2020-35591",
         "Admin bypass in Archer A7 (PLA)"),
    ],
    "Ubiquiti": [
        (r"Ubiquiti[\s/:]*([\d]+\.[\d.]+)", "0", "6.4.6", "CVE-2021-44248",
         "AirOS RCE (unauth)"),
    ],
}


def version_tuple(v):
    parts = []
    for p in re.findall(r"\d+", v)[:4]:
        parts.append(int(p))
    return tuple(parts + [0] * (4 - len(parts)))


def check_cves(vendor, text):
    """Возвращает список CVE для вендора по тексту баннера."""
    rules = CVE_DB.get(vendor, [])
    if not rules or not text:
        return []
    found = []
    for pattern, vmin, vmax, cve, desc in rules:
        m = re.search(pattern, text, re.I)
        if not m:
            continue
        try:
            ver = m.group(1)
            vt = version_tuple(ver)
            if version_tuple(vmin) <= vt <= version_tuple(vmax):
                found.append({"cve": cve, "version": ver, "description": desc})
        except Exception:
            continue
    return found


def main():
    parser = argparse.ArgumentParser(description="CVE mapping for routers")
    parser.add_argument("--ip", help="Проверить один IP")
    parser.add_argument("--refresh", action="store_true", help="Пересчитать для всех")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(scan_routers)")]
    if "cves" not in cols:
        cur.execute("ALTER TABLE scan_routers ADD COLUMN cves TEXT")
        conn.commit()

    if args.ip:
        rows = cur.execute("SELECT ip, vendor, title, banner, server_header FROM scan_routers WHERE ip=?",
                           (args.ip,)).fetchall()
    else:
        rows = cur.execute("SELECT ip, vendor, title, banner, server_header FROM scan_routers").fetchall()

    vulnerable = []
    for ip, vendor, title, banner, srv in rows:
        text = " ".join(x or "" for x in [srv, title, banner])
        cves = check_cves(vendor or "", text)
        cur.execute("UPDATE scan_routers SET cves=? WHERE ip=?", (json.dumps(cves, ensure_ascii=False), ip))
        if cves:
            vulnerable.append((ip, vendor, cves))
    conn.commit()
    conn.close()

    print(f"Проверено: {len(rows)} роутеров | уязвимых: {len(vulnerable)}")
    for ip, vendor, cves in vulnerable:
        for c in cves:
            print(f"  ⚠️ {ip:<16} {vendor:<10} {c['cve']:<18} v{c['version']:<10} {c['description']}")

    # сохраняем отчёт
    with open(os.path.join(BASE_DIR, "CVE_REPORT.md"), "w", encoding="utf-8") as f:
        f.write("# 🛡️ CVE-отчёт по обнаруженным роутерам\n\n")
        f.write(f"**Сформирован:** {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n")
        if vulnerable:
            f.write("| IP | Вендор | CVE | Версия | Описание |\n|---|---|---|---|---|\n")
            for ip, vendor, cves in vulnerable:
                for c in cves:
                    f.write(f"| {ip} | {vendor} | [{c['cve']}](https://nvd.nist.gov/vuln/detail/{c['cve']}) | {c['version']} | {c['description']} |\n")
        else:
            f.write("_Уязвимых устройств по известным CVE не найдено._\n")
    print("CVE_REPORT.md сохранён")


if __name__ == "__main__":
    main()
