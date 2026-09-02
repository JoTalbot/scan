#!/usr/bin/env python3
"""Import scan chunks into the durable results database."""
import os
import sys
import gzip
import glob
import csv
import sqlite3
import argparse
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(BASE_DIR, "isp_cidr.db"))
sys.path.insert(0, BASE_DIR)
from router_detect import detect_router
import observability


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def import_scans(conn, files, dry_run=False):
    cur = conn.cursor()
    imported = 0
    routers_found = 0
    for path in files:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if not rows:
            print(f"  ⚠️ {os.path.basename(path)}: пусто")
            continue
        batch = []
        for r in rows:
            try:
                batch.append((
                    r["ip"], int(r["ip_int"]) if r.get("ip_int") else None,
                    int(r["port"]) if r.get("port") else 80, r.get("status", "closed"),
                    int(r.get("has_banner") or 0), int(r["http_status"]) if r.get("http_status") else None,
                    r.get("server_header"), r.get("title"), r.get("realm"),
                    float(r["response_time_ms"]) if r.get("response_time_ms") else None,
                    int(r["asn"]) if r.get("asn") else None, r.get("isp_name"),
                    r.get("country_code"), r.get("country_name_ru"), r.get("region"),
                    r.get("scanned_at", get_now()), r.get("agent_id", "import"),
                ))
                det = detect_router(server_header=r.get("server_header"), title=r.get("title"), banner=None)
                if det:
                    observability.record_detection(det)
                if det and not dry_run:
                    cur.execute("""
                        INSERT OR REPLACE INTO scan_routers
                        (ip, ip_int, port, http_status, vendor, model, device_type,
                         confidence, matched_on, server_header, title, asn, isp_name,
                         country_code, country_name_ru, region, scanned_at, detected_at,
                         agent_id, machine_id)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (r["ip"], batch[-1][1], batch[-1][2], batch[-1][5],
                          det.get("vendor"), det.get("model"), det.get("device_type"),
                          det.get("confidence"), det.get("matched_on"), r.get("server_header"), r.get("title"),
                          batch[-1][10], batch[-1][11], batch[-1][12], batch[-1][13], batch[-1][14],
                          batch[-1][15], get_now(), r.get("agent_id", "import"), "import"))
                    routers_found += 1
            except (KeyError, ValueError) as e:
                print(f"  ⚠️ пропуск строки: {e}")
                continue
        if not dry_run:
            cur.executemany("""
                INSERT OR REPLACE INTO scan_results
                (ip, ip_int, port, status, has_banner, http_status, server_header,
                 title, realm, response_time_ms, asn, isp_name, country_code,
                 country_name_ru, region, scanned_at, agent_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, batch)
        imported += len(batch)
        print(f"  📥 {os.path.basename(path)}: {len(batch)} записей")
    if not dry_run:
        conn.commit()
    return imported, routers_found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delete-after", action="store_true")
    parser.add_argument("--files", help="Конкретные файлы через запятую")
    args = parser.parse_args()
    files = [f.strip() for f in args.files.split(",")] if args.files else sorted(
        glob.glob(os.path.join(BASE_DIR, "data", "scans", "scan_shard_*.csv.gz")))
    if not files:
        print("Нет чанков scan_shard_*.csv.gz")
        return
    print(f"🔍 Найдено чанков: {len(files)}")
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA busy_timeout = 30000;")
    imported, routers = import_scans(conn, files, args.dry_run)
    conn.close()
    print(f"\n✅ Импортировано: {imported} записей, роутеров: {routers}" + (" (dry-run)" if args.dry_run else ""))
    if args.delete_after and not args.dry_run:
        for f in files:
            os.remove(f)
        print("🗑 Чанки удалены")


if __name__ == "__main__":
    main()
