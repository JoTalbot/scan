#!/usr/bin/env python3
import sys, os, sqlite3, ipaddress, asyncio, argparse, time, re, datetime

from router_detect import detect_router

DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(os.path.dirname(__file__), "isp_cidr.db"))

def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def cleanup_temp_files():
    """Remove temporary artifacts left after scanning: SQLite WAL/SHM/journal,
    __pycache__, .pyc and .tmp files. Keeps only meaningful deliverables."""
    import glob
    base = os.path.dirname(os.path.abspath(__file__))
    removed = []
    patterns = ["*.db-wal", "*.db-shm", "*.db-journal", "*.tmp", "*.pyc"]
    for pat in patterns:
        for p in glob.glob(os.path.join(base, pat)):
            try:
                os.remove(p)
                removed.append(p)
            except OSError:
                pass
    for p in glob.glob(os.path.join(base, "**", "__pycache__"), recursive=True):
        try:
            import shutil
            shutil.rmtree(p)
            removed.append(p)
        except OSError:
            pass
    if removed:
        print(f"🧹 Очищено временных файлов: {len(removed)}")
        for p in removed[:10]:
            print("   -", os.path.relpath(p, base))
    else:
        print("🧹 Временных файлов не найдено")

def init_db(conn):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scan_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT NOT NULL,
        ip_int INTEGER,
        port INTEGER DEFAULT 80,
        status TEXT NOT NULL,
        has_banner INTEGER DEFAULT 0,
        http_status INTEGER,
        server_header TEXT,
        title TEXT,
        banner TEXT,
        realm TEXT,
        response_time_ms REAL,
        asn INTEGER,
        isp_name TEXT,
        country_code TEXT,
        country_name_ru TEXT,
        region TEXT,
        scanned_at TEXT NOT NULL,
        agent_id TEXT,
        machine_id TEXT,
        UNIQUE(ip, port)
    );
    """)
    # Миграция со старой схемы (UNIQUE ip -> UNIQUE ip+port + realm)
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='scan_results'")
    row = cur.fetchone()
    if row and "UNIQUE(ip, port)" not in (row[0] or ""):
        print("🔄 Миграция scan_results: UNIQUE(ip) -> UNIQUE(ip, port) + realm...")
        cur.execute("ALTER TABLE scan_results RENAME TO scan_results_old")
        cur.execute("""
        CREATE TABLE scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            ip_int INTEGER,
            port INTEGER DEFAULT 80,
            status TEXT NOT NULL,
            has_banner INTEGER DEFAULT 0,
            http_status INTEGER,
            server_header TEXT,
            title TEXT,
            banner TEXT,
            realm TEXT,
            response_time_ms REAL,
            asn INTEGER,
            isp_name TEXT,
            country_code TEXT,
            country_name_ru TEXT,
            region TEXT,
            scanned_at TEXT NOT NULL,
            agent_id TEXT,
            machine_id TEXT,
            UNIQUE(ip, port)
        )
        """)
        cur.execute("""
        INSERT INTO scan_results (id, ip, ip_int, port, status, has_banner, http_status,
            server_header, title, banner, realm, response_time_ms, asn, isp_name,
            country_code, country_name_ru, region, scanned_at, agent_id, machine_id)
        SELECT id, ip, ip_int, port, status, has_banner, http_status,
            server_header, title, banner, NULL, response_time_ms, asn, isp_name,
            country_code, country_name_ru, region, scanned_at, agent_id, machine_id
        FROM scan_results_old
        """)
        cur.execute("DROP TABLE scan_results_old")
        conn.commit()
        print("✅ Миграция завершена")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_ip ON scan_results(ip);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_has_banner ON scan_results(has_banner);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_asn ON scan_results(asn);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_cc ON scan_results(country_code);")
    cur.execute("""
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
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_router_vendor ON scan_routers(vendor);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_router_model ON scan_routers(model);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_router_asn ON scan_routers(asn);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_router_cc ON scan_routers(country_code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_router_conf ON scan_routers(confidence);")
    conn.commit()

def fetch_unscanned_ips(conn, batch_size=100000, country=None, asn=None, isp_words=None, ports=None):
    cur = conn.cursor()
    
    # 1. Load already scanned (ip_int, port) pairs for fast in-memory filtering
    cur.execute("SELECT ip_int, port FROM scan_results WHERE ip_int IS NOT NULL")
    scanned_ports = {}
    for ip_i, p in cur.fetchall():
        scanned_ports.setdefault(ip_i, set()).add(p)
    scanned = set(scanned_ports.keys())
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

    # приоритизация: только провайдеры с заданными словами в названии
    # (residential: cable/dsl/fiber/telecom и т.п.) — выше плотность роутеров
    if isp_words:
        like_conds = []
        for w in isp_words:
            like_conds.append("isp_name LIKE ?")
            params.append(f"%{w}%")
        conds.append("(" + " OR ".join(like_conds) + ")")

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
                if ports:
                    have = scanned_ports.get(cur_int, set())
                    if all(p in have for p in ports):
                        continue
                else:
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
                    if ports:
                        have = scanned_ports.get(cur_int, set())
                        if all(p in have for p in ports):
                            continue
                    else:
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

async def scan_one_port(ip, ip_int, port, t0, timeout, agent, machine, meta):
    """Проверка одного порта для цели; возвращает dict результата."""
    req = f"GET / HTTP/1.1\r\nHost: {ip}\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\nConnection: close\r\n\r\n".encode()
    res = {
        "ip": ip, "ip_int": ip_int, "port": port, "status": "closed",
        "has_banner": 0, "http_status": None, "server_header": None, "title": None,
        "banner": None, "realm": None, "response_time_ms": 0.0,
        "asn": meta["asn"], "isp_name": meta["isp_name"], "country_code": meta["country_code"],
        "country_name_ru": meta["country_name_ru"], "region": meta["region"],
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
            # (пункт 8) WWW-Authenticate realm — структурированное хранение
            rm = re.search(r'WWW-Authenticate:\s*Basic\s+realm="([^"]*)"', text, re.IGNORECASE)
            if rm:
                res["realm"] = rm.group(1).strip()[:120]

            # Router device detection
            det = detect_router(server_header=res["server_header"], title=res["title"], banner=text)
            if det:
                res["router_detected"] = det
    except asyncio.TimeoutError:
        res["status"] = "timeout"
    except Exception:
        res["status"] = "closed"
    return res


async def scan_single_target(t, ports=(80,), timeout=2.0, agent="Agent-01", machine="aios"):
    """Проверка цели на нескольких портах параллельно. Возвращает список результатов."""
    ip = t["ip"]
    t0 = time.time()
    meta = {
        "asn": t["asn"], "isp_name": t["isp_name"], "country_code": t["country_code"],
        "country_name_ru": t["country_name_ru"], "region": t["region"],
    }
    results = await asyncio.gather(*[
        scan_one_port(ip, t["ip_int"], port, t0, timeout, agent, machine, meta)
        for port in ports
    ])
    return list(results)

async def db_writer(queue, db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA synchronous = NORMAL;")
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA busy_timeout = 30000;")  # мультимашинность: ждать блокировку
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
    # Router records -> separate scan_routers table
    router_rows = [(
        r["ip"], r["ip_int"], r["port"], r["http_status"],
        r["router_detected"].get("vendor"), r["router_detected"].get("model"),
        r["router_detected"].get("device_type"), r["router_detected"].get("confidence"),
        r["router_detected"].get("matched_on"),
        r["server_header"], r["title"], r["banner"],
        r["response_time_ms"], r["asn"], r["isp_name"], r["country_code"],
        r["country_name_ru"], r["region"], r["scanned_at"], get_now(),
        r["agent_id"], r["machine_id"]
    ) for r in records if r.get("router_detected")]
    if router_rows:
        cur.executemany("""INSERT OR REPLACE INTO scan_routers
            (ip, ip_int, port, http_status, vendor, model, device_type, confidence,
             matched_on, server_header, title, banner, response_time_ms, asn, isp_name,
             country_code, country_name_ru, region, scanned_at, detected_at, agent_id, machine_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", router_rows)
    rows = [(
        r["ip"], r["ip_int"], r["port"], r["status"], r["has_banner"],
        r["http_status"], r["server_header"], r["title"], r["banner"], r.get("realm"),
        r["response_time_ms"], r["asn"], r["isp_name"], r["country_code"],
        r["country_name_ru"], r["region"], r["scanned_at"],
        r["agent_id"], r["machine_id"]
    ) for r in records]
    cur.executemany("INSERT OR REPLACE INTO scan_results (ip, ip_int, port, status, has_banner, http_status, server_header, title, banner, realm, response_time_ms, asn, isp_name, country_code, country_name_ru, region, scanned_at, agent_id, machine_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()

async def run_scan(targets, concurrency=500, ports=(80,), timeout=2.0, agent="Agent-01", machine="aios"):
    """Scan with a FIXED worker pool (scales to millions of targets).

    Targets are consumed from a queue by `concurrency` workers; a separate
    writer task persists results in batches. No per-target task is created,
    so memory stays flat regardless of batch size."""
    work_q = asyncio.Queue(maxsize=concurrency * 4)
    res_q = asyncio.Queue(maxsize=50000)
    w_task = asyncio.create_task(db_writer(res_q, DB_PATH))

    total = len(targets)
    done, banners, opens = 0, 0, 0
    t0 = time.time()

    async def producer():
        for t in targets:
            await work_q.put(t)
        for _ in range(concurrency):
            await work_q.put(None)  # sentinel per worker

    async def worker():
        nonlocal done, banners, opens
        while True:
            t = await work_q.get()
            if t is None:
                return
            res_list = await scan_single_target(t, ports, timeout, agent, machine)
            done += 1
            for res in res_list:
                if res["status"] == "open": opens += 1
                if res["has_banner"]: banners += 1
                await res_q.put(res)
            if done % 250 == 0 or done == total:
                dt = time.time() - t0
                pps = int(done / dt) if dt > 0 else 0
                pct = (done / total) * 100
                print(f"\r🚀 [{pct:5.1f}%] {done:,}/{total:,} | Скорость: {pps:,} IP/сек | Открыто: {opens:,} | Баннеров: {banners:,}", end="", flush=True)

    await asyncio.gather(producer(), *[asyncio.create_task(worker()) for _ in range(concurrency)])
    await res_q.put(None)
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
    p_run.add_argument("--ports", default="80", help="Порты через запятую (напр. 80,8080,8443)")
    p_run.add_argument("--country")
    p_run.add_argument("--asn", type=int)
    p_run.add_argument("--shard", type=int, help="Номер машины (0-based)")
    p_run.add_argument("--shard-total", type=int, default=1, help="Всего машин")
    p_run.add_argument("--isp-words", help="Фильтр провайдеров по словам (через запятую): cable,dsl,fiber")
    sub.add_parser("stats")

    args = parser.parse_args()
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    if args.cmd == "run":
        print(f"\n🔍 Выборка {args.batch:,} несканированных IP из базы данных...")
        isp_words = [w.strip() for w in args.isp_words.split(",")] if args.isp_words else None
        ports = tuple(int(p) for p in args.ports.split(",") if p.strip())
        targets = fetch_unscanned_ips(conn, batch_size=args.batch, country=args.country,
                                      asn=args.asn, isp_words=isp_words, ports=ports)
        if args.shard is not None and args.shard_total > 1:
            total = len(targets)
            part = total // args.shard_total
            start = args.shard * part
            end = start + part if args.shard < args.shard_total - 1 else total
            targets = targets[start:end]
            print(f"⚙️ Шард {args.shard+1}/{args.shard_total}: {len(targets):,} IP (из {total:,})")
        conn.close()
        if not targets:
            print("⚠️ Нет несканированных IP под заданные критерии.")
            return
        print(f"⚡ Запуск сканирования {len(targets):,} IP в {args.concurrency} потоков (Timeout {args.timeout}s)...")
        try:
            asyncio.run(run_scan(targets, concurrency=args.concurrency, ports=ports, timeout=args.timeout))
        finally:
            show_stats()
            cleanup_temp_files()
    elif args.cmd == "stats":
        conn.close()
        show_stats()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
