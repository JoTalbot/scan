#!/usr/bin/env python3
"""
Extract Routers from Existing Scan Results
==========================================
Processes previously scanned records (scan_results with banners) through the
router detection engine and stores detected devices into the separate
`scan_routers` table. Can also re-export the full router inventory to a
gzipped CSV chunk under data/routers/.

Usage:
    python3 extract_routers.py [--limit N] [--no-export] [--stats] [--ip X.X.X.X]
"""

import sys
import os
import re
import gzip
import sqlite3
import argparse
import datetime

from router_detect import detect_router

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(BASE_DIR, "isp_cidr.db"))
ROUTERS_DIR = os.path.join(BASE_DIR, "data", "routers")

ROUTER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scan_routers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL UNIQUE,
    ip_int INTEGER,
    port INTEGER DEFAULT 80,
    http_status INTEGER,
    vendor TEXT,
    model TEXT,
    device_type TEXT,
    confidence TEXT,
    matched_on TEXT,
    server_header TEXT,
    title TEXT,
    banner TEXT,
    response_time_ms REAL,
    asn INTEGER,
    isp_name TEXT,
    country_code TEXT,
    country_name_ru TEXT,
    region TEXT,
    scanned_at TEXT,
    detected_at TEXT,
    agent_id TEXT,
    machine_id TEXT
);
"""


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_db(conn):
    cur = conn.cursor()
    cur.execute(ROUTER_TABLE_SQL)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_router_vendor ON scan_routers(vendor);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_router_model ON scan_routers(model);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_router_asn ON scan_routers(asn);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_router_cc ON scan_routers(country_code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_router_conf ON scan_routers(confidence);")
    conn.commit()


def extract(conn, limit=None, only_ip=None):
    """Run detection over scan_results and persist found routers.
    Returns (processed, detected, skipped_existing).
    """
    cur = conn.cursor()
    cur.execute("SELECT ip FROM scan_routers")
    known = set(row[0] for row in cur.fetchall())

    sql = "SELECT ip, ip_int, port, http_status, server_header, title, banner, response_time_ms, asn, isp_name, country_code, country_name_ru, region, scanned_at, agent_id, machine_id FROM scan_results WHERE has_banner = 1"
    params = []
    if only_ip:
        sql += " AND ip = ?"
        params.append(only_ip)
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))

    cur.execute(sql, params)
    rows = cur.fetchall()

    processed = 0
    detected = 0
    skipped = 0
    inserted = 0
    now = get_now()

    batch = []
    for r in rows:
        ip, ip_int, port, http_status, srv, title, banner, rtt, asn, isp, cc, c_ru, region, scanned_at, agent, machine = r
        processed += 1
        if ip in known:
            skipped += 1
            continue

        det = detect_router(server_header=srv, title=title, banner=banner)
        if not det:
            continue
        detected += 1
        known.add(ip)
        batch.append((
            ip, ip_int, port, http_status,
            det.get("vendor"), det.get("model"), det.get("device_type"),
            det.get("confidence"), det.get("matched_on"),
            srv, title, banner, rtt, asn, isp, cc, c_ru, region,
            scanned_at, now, agent, machine
        ))
        if len(batch) >= 500:
            cur.executemany("""
                INSERT OR IGNORE INTO scan_routers
                (ip, ip_int, port, http_status, vendor, model, device_type, confidence,
                 matched_on, server_header, title, banner, response_time_ms, asn, isp_name,
                 country_code, country_name_ru, region, scanned_at, detected_at, agent_id, machine_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch)
            inserted += len(batch)
            batch.clear()

    if batch:
        cur.executemany("""
            INSERT OR IGNORE INTO scan_routers
            (ip, ip_int, port, http_status, vendor, model, device_type, confidence,
             matched_on, server_header, title, banner, response_time_ms, asn, isp_name,
             country_code, country_name_ru, region, scanned_at, detected_at, agent_id, machine_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch)
        inserted += len(batch)

    conn.commit()
    return processed, detected, skipped, inserted


def export_chunk(conn, agent_id="aios"):
    """Export the full scan_routers inventory to data/routers/scan_routers_<ts>.csv.gz."""
    os.makedirs(ROUTERS_DIR, exist_ok=True)
    cur = conn.cursor()
    cur.execute("""
        SELECT ip, port, http_status, vendor, model, device_type, confidence, matched_on,
               server_header, title, asn, isp_name, country_code, country_name_ru, detected_at
        FROM scan_routers ORDER BY detected_at DESC
    """)
    rows = cur.fetchall()
    if not rows:
        print("ℹ️ Нет записей роутеров для экспорта.")
        return None

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(ROUTERS_DIR, f"scan_routers_{agent_id}_{ts}.csv.gz")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write("IP,Port,HTTP_Status,Vendor,Model,Device_Type,Confidence,Matched_On,Server_Header,Title,ASN,ISP_Name,Country_Code,Country_Name,Detected_At\n")
        for r in rows:
            def q(v):
                v = "" if v is None else str(v)
                if any(c in v for c in '",\n\r'):
                    return '"' + v.replace('"', '""') + '"'
                return v
            f.write(",".join(q(x) for x in r) + "\n")
    print(f"✅ Экспорт роутеров: {path} ({os.path.getsize(path)/1024:.1f} KB, {len(rows):,} записей)")
    return path


def print_stats(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM scan_routers")
    total = cur.fetchone()[0]
    print(f"\n📊 Всего роутеров в базе: {total:,}")
    if not total:
        return
    print("\nТоп вендоров:")
    for r in cur.execute("SELECT COALESCE(vendor, 'Unknown') v, COUNT(*) c FROM scan_routers GROUP BY v ORDER BY c DESC LIMIT 15"):
        print("  %6d  %s" % (r[1], r[0]))
    print("\nПо типам устройств:")
    for r in cur.execute("SELECT COALESCE(device_type, '?') t, COUNT(*) c FROM scan_routers GROUP BY t ORDER BY c DESC"):
        print("  %6d  %s" % (r[1], r[0]))
    print("\nПо уверенности:")
    for r in cur.execute("SELECT confidence, COUNT(*) c FROM scan_routers GROUP BY confidence ORDER BY c DESC"):
        print("  %6d  %s" % (r[1], r[0]))


def main():
    parser = argparse.ArgumentParser(description="Extract routers from existing scan results")
    parser.add_argument("--limit", type=int, help="Process only first N banner records")
    parser.add_argument("--no-export", action="store_true", help="Skip CSV chunk export")
    parser.add_argument("--stats", action="store_true", help="Print stats only")
    parser.add_argument("--ip", help="Process a single IP")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    if args.stats:
        print_stats(conn)
        conn.close()
        return

    processed, detected, skipped, inserted = extract(conn, limit=args.limit, only_ip=args.ip)
    print(f"🔍 Обработано записей: {processed:,}")
    print(f"🛜  Обнаружено роутеров: {detected:,} (добавлено в scan_routers: {inserted:,}, уже было: {skipped:,})")

    if not args.no_export and not args.ip:
        export_chunk(conn)
    print_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
