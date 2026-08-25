#!/usr/bin/env python3
"""
Export scan chunk from worker (шард пушит ТОЛЬКО CSV, не БД!)
================================================================
Читает новые записи scan_results (созданные данным шардом за последние
N минут, по scanned_at) и сохраняет их в data/scans/scan_shard_<id>.csv.gz.
Также экспортирует обнаруженные роутеры в data/routers/.

Используется на исполнителях (CircleCI, E2B), чтобы не пушить
конфликтующую БД — данные сливаются на главной машине через import_chunks.py.

Usage:
    python3 export_chunk.py --agent circleci-shard-0 --since 60
"""
import os
import sys
import gzip
import csv
import sqlite3
import argparse
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(BASE_DIR, "isp_cidr.db"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="shard", help="Идентификатор шарда")
    parser.add_argument("--since", type=int, default=90, help="Сколько минут назад брать записи")
    parser.add_argument("--out", default=None, help="Путь к выходному файлу (по умолчанию data/scans/)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    since_ts = (datetime.datetime.now(datetime.timezone.utc) -
                datetime.timedelta(minutes=args.since)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # новые записи (по времени сканирования)
    rows = cur.execute("""
        SELECT ip, ip_int, port, status, has_banner, http_status, server_header,
               title, realm, response_time_ms, asn, isp_name, country_code,
               country_name_ru, region, scanned_at, agent_id
        FROM scan_results WHERE scanned_at >= ?
        ORDER BY id ASC
    """, (since_ts,)).fetchall()

    if not rows:
        print("ℹ️ Нет новых записей с", since_ts)
        conn.close()
        return

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = args.out or os.path.join(BASE_DIR, "data", "scans")
    os.makedirs(out_dir, exist_ok=True)
    chunk = os.path.join(out_dir, f"scan_shard_{args.agent}_{ts}.csv.gz")

    with gzip.open(chunk, "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ip", "ip_int", "port", "status", "has_banner", "http_status",
                    "server_header", "title", "realm", "response_time_ms", "asn",
                    "isp_name", "country_code", "country_name_ru", "region",
                    "scanned_at", "agent_id"])
        for r in rows:
            w.writerow([r["ip"], r["ip_int"], r["port"], r["status"], r["has_banner"],
                        r["http_status"], r["server_header"], r["title"], r["realm"],
                        r["response_time_ms"], r["asn"], r["isp_name"], r["country_code"],
                        r["country_name_ru"], r["region"], r["scanned_at"], r["agent_id"]])

    # роутеры этого шарда
    routers = cur.execute("""
        SELECT ip, vendor, model, device_type, confidence, matched_on, server_header,
               title, asn, isp_name, country_code, country_name_ru
        FROM scan_routers WHERE detected_at >= ?
    """, (since_ts,)).fetchall()
    if routers:
        rdir = os.path.join(BASE_DIR, "data", "routers")
        os.makedirs(rdir, exist_ok=True)
        rchunk = os.path.join(rdir, f"scan_routers_shard_{args.agent}_{ts}.csv.gz")
        with gzip.open(rchunk, "wt", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ip", "vendor", "model", "device_type", "confidence",
                        "matched_on", "server_header", "title", "asn", "isp_name",
                        "country_code", "country_name_ru"])
            for r in routers:
                w.writerow([r["ip"], r["vendor"], r["model"], r["device_type"],
                            r["confidence"], r["matched_on"], r["server_header"],
                            r["title"], r["asn"], r["isp_name"], r["country_code"],
                            r["country_name_ru"]])
        print(f"🛜  Роутеров в чанке: {len(routers)} -> {rchunk}")
    conn.close()

    print(f"✅ Чанк: {chunk} ({len(rows)} записей, {os.path.getsize(chunk)/1024:.1f} KB)")
    print(f"   Пушится: git add data/ && git commit && git push")


if __name__ == "__main__":
    main()
