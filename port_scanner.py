#!/usr/bin/env python3
import sys, os, sqlite3, ipaddress, asyncio, argparse, time, re, datetime

DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(os.path.dirname(__file__), "isp_cidr.db"))

def get_now():
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_asn ON scan_results(asn);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_cc ON scan_results(country_code);")
    conn.commit()

def fetch_unscanned_ips(conn, batch_size=100000, country=None, asn=None):
    cur = conn.cursor()
    
    # 1. Load already scanned IP integers for fast in-memory filtering
    cur.execute("SELECT ip_int FROM scan_results WHERE ip_int IS NOT NULL")
    scanned = set(row[0] for row in cur.fetchall())
    print(f"ℹ️ Уже в базе просканировано: {len(scanned):,} IP")

    # 2. Universal query across v_ip_ranges / ip_ranges
    conds = ["start_ip_int IS NOT NULL AND start_ip_int > 0"]
    params = []
    if country:
        conds.append("country_code = ?")
        params.append(country.upper())
    if asn:
        conds.append("asn = ?")
        params.append(int(asn))

    where = " WHERE " + " AND ".join(conds)

    # Try v_ip_ranges first, fallback to ip_ranges
    try:
        cur.execute(f"SELECT start_ip_int, end_ip_int, asn, isp_name, country_code, country_name_ru, region FROM v_ip_ranges {where} ORDER BY RANDOM() LIMIT 25000", params)
        ranges = cur.fetchall()
    except Exception:
        cur.execute(f"SELECT start_ip_int, end_ip_int, 0, 'Unknown', 'XX', 'Unknown', 'Unknown' FROM ip_ranges {where} ORDER BY RANDOM() LIMIT 25000", params)
        ranges = cur.fetchall()

    if not ranges:
        # Fallback without random
        cur.execute("SELECT start_ip_int, end_ip_int, 0, 'Unknown', 'XX', 'Unknown', 'Unknown' FROM ip_ranges WHERE start_ip_int IS NOT NULL LIMIT 25000")
        ranges = cur.fetchall()

    targets = []
    for r in ranges:
        s_int, e_int, a_val, isp, cc, c_ru, reg = r
        if not s_int or not e_int or e_int < s_int:
            continue
        total = e_int - s_int + 1
        
        # Stride per subnet to sample evenly
        step = max(1, total // 16) if total > 32 else 1
        for cur_int in range(s_int, e_int + 1, step):
            if cur_int in scanned:
                continue
            scanned.add(cur_int)
            targets.append({
                "ip": str(ipaddress.IPv4Address(cur_int)),
                "ip_int": cur_int,
                "asn": a_val,
                "isp_name": isp,
                "country_code": cc,
                "country_name_ru": c_ru,
                "region": reg
            })
            if len(targets) >= batch_size:
                return targets

    # If stride didn't reach batch_size, fill sequentially
    if len(targets) < batch_size:
        for r in ranges:
            s_int, e_int, a_val, isp, cc, c_ru, reg = r
            if not s_int or not e_int: continue
            for cur_int in range(s_int, e_int + 1):
                if cur_int in scanned:
                    continue
                scanned.add(cur_int)
                targets.append({
                    "ip": str(ipaddress.IPv4Address(cur_int)),
                    "ip_int": cur_int,
                    "asn": a_val,
                    "isp_name": isp,
                    "country_code": cc,
                    "country_name_ru": c_ru,
                    "region": reg
                })
                if len(targets) >= batch_size:
                    return targets

    return targets

async def scan_single_target(t, port=80, timeout=2.0, agent="Agent-01", machine="aios"):
    ip = t["ip"]
    t0 = time.time()
    req = f"GET / HTTP/1.1\r\nHost: {ip}\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\nConnection: close\r\n\r\n".encode()
    res = {
        "ip": ip, "ip_int": t["ip_int"], "port": port, "status": "closed",
        "has_banner": 0, "http_status": None, "server_header": None, "title": None,
        "banner": None, "response_time_ms": 0.0, "asn": t["asn"],
        "isp_name": t["isp_name"], "country_code": t["country_code"],
        "country_name_ru": t["country_name_ru"], "region": t["region"],
        "scanned_at": get_now(), "agent_id": agent, "machine_id": machine
    }
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        res["status"] = "open"
        writer.write(req)
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(4096), timeout=timeout)
        res["response_time_ms"] = round((time.time() - t0) * 1000, 2)
        writer.close()
        try: await writer.wait_closed()
        except Exception: pass

        if raw:
            text = raw.decode("utf-8", errors="ignore")
            res["has_banner"] = 1
            res["banner"] = text[:1500]
            sm = re.search(r"HTTP/\d\.\d\s+(\d{3})", text)
            if sm: res["http_status"] = int(sm.group(1))
            srv = re.search(r"(?i)^server:\s*(.+)$", text, re.MULTILINE)
            if srv: res["server_header"] = srv.group(1).strip()[:100]
            tm = re.search(r"(?i)<title[^>]*>(.*?)</title>", text, re.DOTALL)
            if tm: res["title"] = re.sub(r"\s+", " ", tm.group(1)).strip()[:200]
    except asyncio.TimeoutError:
        res["status"] = "timeout"
    except Exception:
        res["status"] = "closed"
    return res

async def db_writer(queue, db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA synchronous = NORMAL;")
    cur.execute("PRAGMA journal_mode = WAL;")
    batch = []
    while True:
        item = await queue.get()
        if item is None:
            if batch: flush(cur, conn, batch)
            break
        batch.append(item)
        if len(batch) >= 200:
            flush(cur, conn, batch)
            batch.clear()
    conn.close()

def flush(cur, conn, records):
    rows = [(
        r["ip"], r["ip_int"], r["port"], r["status"], r["has_banner"],
        r["http_status"], r["server_header"], r["title"], r["banner"],
        r["response_time_ms"], r["asn"], r["isp_name"], r["country_code"],
        r["country_name_ru"], r["region"], r["scanned_at"],
        r["agent_id"], r["machine_id"]
    ) for r in records]
    cur.executemany("INSERT OR REPLACE INTO scan_results (ip, ip_int, port, status, has_banner, http_status, server_header, title, banner, response_time_ms, asn, isp_name, country_code, country_name_ru, region, scanned_at, agent_id, machine_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()

async def run_scan(targets, concurrency=500, port=80, timeout=2.0, agent="Agent-01", machine="aios"):
    sem = asyncio.Semaphore(concurrency)
    q = asyncio.Queue(maxsize=50000)
    w_task = asyncio.create_task(db_writer(q, DB_PATH))

    total = len(targets)
    done, banners, opens = 0, 0, 0
    t0 = time.time()

    async def worker(t):
        nonlocal done, banners, opens
        async with sem:
            res = await scan_single_target(t, port, timeout, agent, machine)
            done += 1
            if res["status"] == "open": opens += 1
            if res["has_banner"]: banners += 1
            await q.put(res)
            if done % 250 == 0 or done == total:
                dt = time.time() - t0
                pps = int(done / dt) if dt > 0 else 0
                pct = (done / total) * 100
                print(f"\r🚀 [{pct:5.1f}%] {done:,}/{total:,} | Скорость: {pps:,} IP/сек | Открыто: {opens:,} | Баннеров: {banners:,}", end="", flush=True)

    tasks = [asyncio.create_task(worker(t)) for t in targets]
    await asyncio.gather(*tasks)
    await q.put(None)
    await w_task
    print(f"\n\n✨ Сканирование завершено за {time.time()-t0:.2f}с! Найдено баннеров: {banners:,}")

def show_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM scan_results")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS banners FROM scan_results WHERE has_banner = 1")
    banners = cur.fetchone()["banners"]
    print(f"\n📊 Всего проверено IP: {total:,} | Найдено веб-баннеров: {banners:,}")
    if banners > 0:
        print("\nТоп Web-серверов:")
        cur.execute("SELECT COALESCE(server_header, 'Скрыт') AS srv, COUNT(*) AS cnt FROM scan_results WHERE has_banner = 1 GROUP BY srv ORDER BY cnt DESC LIMIT 6")
        for r in cur.fetchall():
            print(f"  • {r['srv']:<30} : {r['cnt']:,}")
    conn.close()

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    p_run = sub.add_parser("run")
    p_run.add_argument("--batch", type=int, default=100000)
    p_run.add_argument("--concurrency", type=int, default=500)
    p_run.add_argument("--timeout", type=float, default=2.0)
    p_run.add_argument("--country")
    p_run.add_argument("--asn", type=int)
    sub.add_parser("stats")

    args = parser.parse_args()
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    if args.cmd == "run":
        print(f"\n🔍 Выборка {args.batch:,} несканированных IP из базы данных...")
        targets = fetch_unscanned_ips(conn, batch_size=args.batch, country=args.country, asn=args.asn)
        conn.close()
        if not targets:
            print("⚠️ Нет несканированных IP под заданные критерии.")
            return
        print(f"⚡ Запуск сканирования {len(targets):,} IP в {args.concurrency} потоков (Timeout {args.timeout}s)...")
        asyncio.run(run_scan(targets, concurrency=args.concurrency, port=80, timeout=args.timeout))
        show_stats()
    elif args.cmd == "stats":
        conn.close()
        show_stats()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
