#!/usr/bin/env python3
"""
High-Speed Asynchronous Port 80 & Banner Scanner (500+ Concurrent Streams)
Pulls unvisited IPs from `ip_ranges`, scans port 80, extracts HTTP banners, and saves to `scan_results`.
"""

import sys
import os
import sqlite3
import ipaddress
import asyncio
import argparse
import time
import re
import datetime

DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(os.path.dirname(__file__), "isp_cidr.db"))
DEFAULT_CONCURRENCY = 500
DEFAULT_TIMEOUT = 2.0

def get_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def init_db(conn):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scan_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT NOT NULL UNIQUE,
        ip_int INTEGER,
        port INTEGER DEFAULT 80,
        status TEXT NOT NULL,
        has_banner INTEGER DEFAULT 0,
        http_status INTEGER,
        server_header TEXT,
        title TEXT,
        banner TEXT,
        response_time_ms REAL,
        asn INTEGER,
        isp_name TEXT,
        country_code TEXT,
        country_name_ru TEXT,
        region TEXT,
        scanned_at TEXT NOT NULL,
        agent_id TEXT,
        machine_id TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_ip ON scan_results(ip);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_has_banner ON scan_results(has_banner);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_server ON scan_results(server_header);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_asn ON scan_results(asn);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_cc ON scan_results(country_code);")
    conn.commit()

def fetch_unscanned_ips(conn, batch_size=10000, country=None, region=None, asn=None):
    cur = conn.cursor()
    conds = ["c.ip_version = 4"]
    params = []
    if country:
        conds.append("c.country_code = ?")
        params.append(country.upper())
    if region:
        conds.append("cnt.region = ?")
        params.append(region)
    if asn:
        conds.append("c.asn = ?")
        params.append(int(asn))

    where = " WHERE " + " AND ".join(conds)
    query = f"""
    SELECT r.start_ip_int, r.end_ip_int, c.asn, COALESCE(p.org_name, 'Unknown') AS isp_name,
           c.country_code, cnt.country_name_ru, cnt.region
    FROM ip_ranges r
    JOIN cidr_blocks c ON r.cidr_id = c.id
    LEFT JOIN providers p ON c.asn = p.asn
    LEFT JOIN countries cnt ON c.country_code = cnt.country_code
    {where}
    ORDER BY RANDOM()
    LIMIT 2000
    """
    cur.execute(query, params)
    ranges = cur.fetchall()

    if not ranges:
        return []

    cur.execute("SELECT ip_int FROM scan_results WHERE ip_int IS NOT NULL")
    scanned_set = set(row[0] for row in cur.fetchall())

    candidate_ips = []
    for r in ranges:
        s_int, e_int, asn_val, isp_name, cc, c_ru, reg = r
        total = e_int - s_int + 1
        step = max(1, total // 8) if total > 16 else 1
        for current_int in range(s_int, e_int + 1, step):
            if current_int in scanned_set:
                continue
            candidate_ips.append({
                "ip": str(ipaddress.IPv4Address(current_int)),
                "ip_int": current_int,
                "asn": asn_val,
                "isp_name": isp_name,
                "country_code": cc,
                "country_name_ru": c_ru,
                "region": reg
            })
            if len(candidate_ips) >= batch_size:
                break
        if len(candidate_ips) >= batch_size:
            break

    return candidate_ips

async def scan_single_target(target, port=80, timeout=2.0, agent_id="Agent-Scanner", machine_id="Host-01"):
    ip = target["ip"]
    t0 = time.time()
    req = (
        f"GET / HTTP/1.1\r\n"
        f"Host: {ip}\r\n"
        f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
        f"Accept: text/html,application/xhtml+xml,*/*\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8")

    result = {
        "ip": ip, "ip_int": target["ip_int"], "port": port, "status": "closed",
        "has_banner": 0, "http_status": None, "server_header": None, "title": None,
        "banner": None, "response_time_ms": 0.0, "asn": target["asn"],
        "isp_name": target["isp_name"], "country_code": target["country_code"],
        "country_name_ru": target["country_name_ru"], "region": target["region"],
        "scanned_at": get_now_iso(), "agent_id": agent_id, "machine_id": machine_id
    }

    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        result["status"] = "open"
        writer.write(req)
        await writer.drain()

        raw_data = await asyncio.wait_for(reader.read(4096), timeout=timeout)
        result["response_time_ms"] = round((time.time() - t0) * 1000, 2)

        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

        if raw_data:
            text = raw_data.decode("utf-8", errors="ignore")
            result["has_banner"] = 1
            result["banner"] = text[:1500]

            status_match = re.search(r"HTTP/\d\.\d\s+(\d{3})", text)
            if status_match:
                result["http_status"] = int(status_match.group(1))

            server_match = re.search(r"(?i)^server:\s*(.+)$", text, re.MULTILINE)
            if server_match:
                result["server_header"] = server_match.group(1).strip()[:100]

            title_match = re.search(r"(?i)<title[^>]*>(.*?)</title>", text, re.DOTALL)
            if title_match:
                result["title"] = re.sub(r"\s+", " ", title_match.group(1)).strip()[:200]

    except asyncio.TimeoutError:
        result["status"] = "timeout"
    except (ConnectionRefusedError, OSError):
        result["status"] = "closed"
    except Exception as e:
        result["status"] = f"error: {type(e).__name__}"

    return result

async def run_scanner_pool(targets, concurrency=500, port=80, timeout=2.0, agent_id="Agent-01", machine_id="Machine-01"):
    semaphore = asyncio.Semaphore(concurrency)
    total_targets = len(targets)
    completed = 0
    banners_found = 0
    start_time = time.time()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA synchronous = NORMAL;")
    cur.execute("PRAGMA journal_mode = WAL;")

    buffer_results = []

    async def worker(target):
        nonlocal completed, banners_found
        async with semaphore:
            res = await scan_single_target(target, port, timeout, agent_id, machine_id)
            completed += 1
            if res["has_banner"]:
                banners_found += 1
            buffer_results.append(res)

            if len(buffer_results) >= 100:
                flush_to_db(conn, buffer_results)
                buffer_results.clear()

            if completed % 250 == 0 or completed == total_targets:
                elapsed = time.time() - start_time
                pps = int(completed / elapsed) if elapsed > 0 else 0
                pct = (completed / total_targets) * 100
                print(
                    f"\r🚀 [{pct:5.1f}%] Scanned: {completed:,}/{total_targets:,} | "
                    f"Speed: {pps:,} IPs/sec | "
                    f"Banners Found: {banners_found:,}",
                    end="",
                    flush=True
                )

    tasks = [asyncio.create_task(worker(t)) for t in targets]
    await asyncio.gather(*tasks)

    if buffer_results:
        flush_to_db(conn, buffer_results)
        buffer_results.clear()

    conn.close()
    elapsed = time.time() - start_time
    print(f"\n\n✨ Scan Completed in {elapsed:.2f}s! Total Banners: {banners_found:,}")

def flush_to_db(conn, records):
    cur = conn.cursor()
    rows = [
        (
            r["ip"], r["ip_int"], r["port"], r["status"], r["has_banner"],
            r["http_status"], r["server_header"], r["title"], r["banner"],
            r["response_time_ms"], r["asn"], r["isp_name"], r["country_code"],
            r["country_name_ru"], r["region"], r["scanned_at"],
            r["agent_id"], r["machine_id"]
        )
        for r in records
    ]
    cur.executemany("""
    INSERT OR REPLACE INTO scan_results (
        ip, ip_int, port, status, has_banner,
        http_status, server_header, title, banner,
        response_time_ms, asn, isp_name, country_code,
        country_name_ru, region, scanned_at, agent_id, machine_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()

def show_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM scan_results")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS banners FROM scan_results WHERE has_banner = 1")
    banners = cur.fetchone()["banners"]

    print("\n📊 SCAN RESULTS STATS")
    print("=" * 60)
    print(f"Total Scanned IPs:     {total:,}")
    print(f"Banners / Web Servers: {banners:,}")
    if banners > 0:
        print("\nTop Web Server Headers:")
        cur.execute("""
            SELECT COALESCE(server_header, 'Unknown/Hidden') AS srv, COUNT(*) AS count
            FROM scan_results WHERE has_banner = 1 GROUP BY srv ORDER BY count DESC LIMIT 8
        """)
        for r in cur.fetchall():
            print(f"  • {r['srv']:<35} : {r['count']:,}")
    print("=" * 60)
    conn.close()

def export_results(out_file, only_banners=True):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    where = "WHERE has_banner = 1" if only_banners else ""
    cur.execute(f"""
        SELECT ip, port, http_status, server_header, title, asn, isp_name,
               country_code, country_name_ru, response_time_ms, scanned_at
        FROM scan_results {where} ORDER BY id DESC
    """)
    rows = cur.fetchall()
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("IP,Port,HTTP_Status,Server_Header,Page_Title,ASN,ISP_Name,Country_Code,Country_Name,Latency_MS,Scanned_At\n")
        for r in rows:
            title_clean = (r[4] or "").replace('"', '""')
            isp_clean = (r[6] or "").replace('"', '""')
            srv_clean = (r[3] or "").replace('"', '""')
            f.write(f'{r[0]},{r[1]},{r[2] or ""},"{srv_clean}","{title_clean}",{r[5]},"{isp_clean}",{r[7]},{r[8]},{r[9]},{r[10]}\n')
    conn.close()
    print(f"📁 Exported {len(rows)} records to {out_file}")

def main():
    parser = argparse.ArgumentParser(description="High-Speed Async Port 80 & Banner Scanner")
    subparsers = parser.add_subparsers(dest="cmd", help="Command")

    p_run = subparsers.add_parser("run", help="Run high-speed scan")
    p_run.add_argument("--batch", type=int, default=10000, help="Number of unscanned IPs to process")
    p_run.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Parallel streams (default: 500)")
    p_run.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Connection timeout (default: 2.0s)")
    p_run.add_argument("--country", help="Filter by country (e.g. UA, US, DE)")
    p_run.add_argument("--region", help="Filter by region (Ukraine, Europe, United States)")
    p_run.add_argument("--asn", type=int, help="Filter by ASN")
    p_run.add_argument("--agent", default="Agent-Scanner-01", help="Agent identifier")
    p_run.add_argument("--machine", default="Machine-01", help="Machine identifier")

    subparsers.add_parser("stats", help="Display scan summary statistics")

    p_exp = subparsers.add_parser("export", help="Export found banners to CSV")
    p_exp.add_argument("--out", required=True, help="Output CSV path")
    p_exp.add_argument("--all", action="store_true", help="Include closed/timeout hosts too")

    args = parser.parse_args()
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    if args.cmd == "run":
        print(f"\n🔍 Selecting {args.batch:,}+ unscanned IPs from `ip_ranges`...")
        targets = fetch_unscanned_ips(conn, batch_size=args.batch, country=args.country, region=args.region, asn=args.asn)
        conn.close()
        if not targets:
            print("⚠️ No unscanned IPs found matching criteria.")
            return

        print(f"⚡ Ready to scan {len(targets):,} IPs with {args.concurrency} parallel async workers (Port 80)...")
        asyncio.run(run_scanner_pool(
            targets, concurrency=args.concurrency, port=80, timeout=args.timeout,
            agent_id=args.agent, machine_id=args.machine
        ))
        show_stats()
    elif args.cmd == "stats":
        conn.close()
        show_stats()
    elif args.cmd == "export":
        conn.close()
        export_results(args.out, only_banners=not args.all)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
