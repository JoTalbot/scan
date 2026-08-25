#!/usr/bin/env python3
"""
Cleanup: удаление записей, не относящихся к роутерам
=====================================================
1. scan_results: удаляет все записи, чьи IP не входят в scan_routers
   (оставляем только роутерные IP — ~1300 записей вместо 3.5M).
2. data/scans/*.csv.gz: удаляет старые чанки (уже в git).
3. VACUUM для сжатия БД.

ВАЖНО: после очистки дедупликация сканов сбросится — сканер снова
сможет сканировать те же IP. БД станет компактной (роутер-фокус).

Usage:
    python3 cleanup_non_routers.py [--dry-run] [--keep-chunks]
"""
import os
import sys
import glob
import sqlite3
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "isp_cidr.db")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Только показать, что удалится")
    parser.add_argument("--keep-chunks", action="store_true", help="Не удалять CSV-чанки")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA busy_timeout = 30000;")
    cur = conn.cursor()

    # 1. роутерные IP
    cur.execute("SELECT COUNT(*) FROM scan_routers")
    routers = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM scan_results")
    total = cur.fetchone()[0]

    # удаляем не-роутерные записи
    sql = """DELETE FROM scan_results
             WHERE ip NOT IN (SELECT ip FROM scan_routers)"""
    if args.dry_run:
        cur.execute("SELECT COUNT(*) FROM scan_results WHERE ip NOT IN (SELECT ip FROM scan_routers)")
        to_del = cur.fetchone()[0]
        print(f"[dry-run] Роутеров: {routers} | scan_results: {total} | будет удалено: {to_del}")
        conn.close()
        return

    cur.execute(sql)
    deleted = cur.rowcount
    conn.commit()

    # 2. старые чанки
    chunks_removed = 0
    if not args.keep_chunks:
        for pat in ["data/scans/scan_*.csv.gz", "data/routers/scan_*_shard_*.csv.gz"]:
            for f in glob.glob(os.path.join(BASE_DIR, pat)):
                if args.dry_run:
                    print(f"  [dry-run] чанк: {f}")
                else:
                    os.remove(f)
                    chunks_removed += 1

    # 3. VACUUM
    if not args.dry_run:
        before = os.path.getsize(DB_PATH) / 1024 / 1024
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        after = os.path.getsize(DB_PATH) / 1024 / 1024
        print(f"🗜 VACUUM: {before:.1f} МБ -> {after:.1f} МБ")
    conn.close()

    cur = None
    print(f"✅ Удалено записей не-роутеров: {deleted} | чанков: {chunks_removed}")
    print(f"   Осталось роутеров: {routers}")


if __name__ == "__main__":
    main()
