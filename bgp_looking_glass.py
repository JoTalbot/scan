#!/usr/bin/env python3
"""
BGP Looking Glass — интеграция с RIPE Stat API
==============================================
Отслеживание BGP-анонсов в реальном времени (без ключей, публичный API):

  * Получить текущие анонсируемые префиксы ASN      (announced-prefixes)
  * Узнать origin-AS для IP/префикса                 (route-origin)
  * Сравнить актуальные анонсы с нашей БД            (--check-db)
    -> обнаружить префиксы, которых нет в isp_cidr.db (новые анонсы)
    -> и префиксы из БД, которые уже не анонсируются (устаревшие)

Usage:
    python3 bgp_looking_glass.py --asn 3320
    python3 bgp_looking_glass.py --ip 8.8.8.8
    python3 bgp_looking_glass.py --check-db --asn 3320
    python3 bgp_looking_glass.py --top-differs 5   # ТОП ASN по расхождению БД vs реальность
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
UA = "Mozilla/5.0 (RouterScan Project)"


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ripe_get(endpoint, params, timeout=15):
    """GET к RIPE Stat API. Возвращает dict или None."""
    url = f"https://stat.ripe.net/data/{endpoint}/data.json?" + "&".join(
        f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ⚠️ RIPE Stat error: {e}")
        return None


def get_announced_prefixes(asn):
    """Актуальные анонсируемые префиксы ASN (IPv4+IPv6)."""
    data = ripe_get("announced-prefixes", {"resource": f"AS{asn}"})
    if not data or "data" not in data:
        return []
    return [p["prefix"] for p in data["data"].get("prefixes", [])]


def get_origin_as(ip):
    """Origin-AS для IP (routing-status: origin + видимость)."""
    data = ripe_get("routing-status", {"resource": ip})
    if not data or "data" not in data:
        return None
    d = data["data"]
    return {
        "prefix": d.get("first_seen", {}).get("prefix"),
        "origin": d.get("first_seen", {}).get("origin"),
        "visibility": d.get("visibility", {}),
        "announced": d.get("announced", False),
    }


def db_prefixes_for_asn(conn, asn):
    """Префиксы из БД для ASN (cidr_blocks)."""
    cur = conn.cursor()
    return [r[0] for r in cur.execute(
        "SELECT cidr FROM cidr_blocks WHERE asn = ?", (int(asn),)).fetchall()]


def check_asn(conn, asn, verbose=True):
    """Сравнение актуальных BGP-анонсов с БД."""
    live = set(get_announced_prefixes(asn))
    if not live:
        return None
    db_set = set(db_prefixes_for_asn(conn, asn))
    missing_in_db = sorted(live - db_set)   # есть в BGP, нет в БД
    stale_in_db = sorted(db_set - live)     # есть в БД, нет в BGP
    if verbose:
        print(f"AS{asn}: анонсов в BGP: {len(live)}, в БД: {len(db_set)}")
        if missing_in_db:
            print(f"  🆕 НОВЫЕ анонсы (нет в БД): {len(missing_in_db)}")
            for p in missing_in_db[:10]:
                print(f"     + {p}")
        if stale_in_db:
            print(f"  🗑  Устаревшие (нет в BGP): {len(stale_in_db)}")
            for p in stale_in_db[:10]:
                print(f"     - {p}")
    return {"asn": asn, "live": len(live), "db": len(db_set),
            "new": len(missing_in_db), "stale": len(stale_in_db)}


def update_db(conn, asn, dry_run=False):
    """№4: добавить недостающие префиксы ASN из BGP в cidr_blocks + ip_ranges."""
    import ipaddress
    live = set(get_announced_prefixes(asn))
    if not live:
        print(f"AS{asn}: нет анонсов (или ошибка API)")
        return 0
    db_set = set(db_prefixes_for_asn(conn, asn))
    missing = sorted(live - db_set)
    if not missing:
        print(f"AS{asn}: БД актуальна ({len(db_set)} префиксов)")
        return 0
    # страна ASN из providers
    cur = conn.cursor()
    row = cur.execute("SELECT country_code FROM providers WHERE asn = ?", (int(asn),)).fetchone()
    cc = row[0] if row else "ZZ"
    if dry_run:
        print(f"AS{asn}: будет добавлено {len(missing)} префиксов (страна {cc}):")
        for p in missing[:10]:
            print(f"  + {p}")
        return len(missing)
    added = 0
    for cidr in missing:
        try:
            net = ipaddress.ip_network(cidr, strict=False)
        except Exception:
            continue
        ver = net.version
        total = net.num_addresses if ver == 4 else 0
        cur.execute("INSERT OR IGNORE INTO cidr_blocks (cidr, ip_version, asn, country_code, total_ips) VALUES (?,?,?,?,?)",
                    (cidr, ver, int(asn), cc, total))
        if cur.rowcount == 0:
            continue
        cidr_id = cur.lastrowid
        if ver == 4:
            cur.execute("""INSERT OR IGNORE INTO ip_ranges
                (cidr_id, start_ip, end_ip, start_ip_int, end_ip_int, netmask, wildcard_mask)
                VALUES (?,?,?,?,?,?,?)""",
                (cidr_id, str(net.network_address), str(net.broadcast_address),
                 int(net.network_address), int(net.broadcast_address),
                 str(net.netmask), str(net.hostmask)))
        added += 1
    conn.commit()
    print(f"AS{asn}: добавлено {added} префиксов (из {len(missing)} отсутствующих)")
    return added


def main():
    parser = argparse.ArgumentParser(description="BGP Looking Glass (RIPE Stat)")
    parser.add_argument("--asn", type=int, help="Проверить конкретный ASN")
    parser.add_argument("--ip", help="Определить origin-AS по IP")
    parser.add_argument("--check-db", action="store_true", help="Сравнить с БД")
    parser.add_argument("--top-differs", type=int, help="ТОП-N ASN из БД по расхождению с BGP")
    parser.add_argument("--update-db", action="store_true", help="Добавить недостающие префиксы ASN в БД")
    parser.add_argument("--dry-run", action="store_true", help="Показать без записи")
    parser.add_argument("--limit", type=int, default=20, help="Сколько ASN проверить для top-differs")
    args = parser.parse_args()

    import urllib.parse  # noqa

    if args.ip:
        info = get_origin_as(args.ip)
        if info and info.get("origin"):
            vis = info.get("visibility") or {}
            print(f"IP {args.ip} -> префикс {info['prefix']}, origin AS{info['origin']}, "
                  f"анонсирован: {info['announced']}, видимость: {vis.get('v4', {}).get('total_ris_peers_seeing', '?')} RIS-пиров")
        else:
            print(f"IP {args.ip} -> не найден")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if args.asn:
        if args.update_db:
            update_db(conn, args.asn, dry_run=args.dry_run)
        elif args.check_db:
            check_asn(conn, args.asn)
        else:
            prefixes = get_announced_prefixes(args.asn)
            print(f"AS{args.asn}: {len(prefixes)} префиксов")
            for p in prefixes[:20]:
                print(f"  {p}")
        conn.close()
        return

    if args.top_differs:
        print(f"Проверяю ТОП-{args.limit} ASN из БД по объёму префиксов...")
        asns = [r[0] for r in cur.execute(
            "SELECT asn, COUNT(*) c FROM cidr_blocks WHERE asn IS NOT NULL "
            "GROUP BY asn ORDER BY c DESC LIMIT ?", (args.limit,)).fetchall()]
        results = []
        for i, asn in enumerate(asns):
            r = check_asn(conn, asn, verbose=False)
            if r:
                results.append(r)
            print(f"  [{i+1}/{len(asns)}] AS{asn} checked", end="\r")
            time.sleep(0.3)
        print()
        results.sort(key=lambda x: x["new"] + x["stale"], reverse=True)
        print("\n=== ТОП расхождений БД vs BGP ===")
        print(f"{'ASN':<12} {'BGP':<8} {'БД':<8} {'Новые':<8} {'Устаревшие':<10}")
        for r in results[:args.top_differs]:
            print(f"AS{r['asn']:<10} {r['live']:<8} {r['db']:<8} {r['new']:<8} {r['stale']:<10}")
        conn.close()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
