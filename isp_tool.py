#!/usr/bin/env python3
"""
ISP CIDR Database Tool - Query, Search, and Export Tool
Supports Ukraine, USA, and European Countries.
"""

import sys
import os
import sqlite3
import ipaddress
import argparse
import json
import csv

DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(os.path.dirname(__file__), "isp_cidr.db"))

def get_db():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ip_lookup(ip_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())
    except ValueError as e:
        return {"error": f"Invalid IP address: {e}"}

    conn = get_db()
    cur = conn.cursor()

    if ip_obj.version == 4:
        ip_int = int(ip_obj)
        cur.execute("""
            SELECT 
                c.id, c.cidr, c.ip_version, c.asn,
                COALESCE(p.org_name, 'Unknown Provider') AS isp_name,
                c.country_code, cnt.country_name_en, cnt.country_name_ru, cnt.region,
                c.start_ip, c.end_ip, c.ip_count
            FROM cidr_blocks c
            LEFT JOIN providers p ON c.asn = p.asn
            LEFT JOIN countries cnt ON c.country_code = cnt.country_code
            WHERE c.ip_version = 4 AND c.start_ip_int <= ? AND c.end_ip_int >= ?
            ORDER BY (c.end_ip_int - c.start_ip_int) ASC
            LIMIT 1
        """, (ip_int, ip_int))
        row = cur.fetchone()
    else:
        # IPv6 lookup
        cur.execute("""
            SELECT 
                c.id, c.cidr, c.ip_version, c.asn,
                COALESCE(p.org_name, 'Unknown Provider') AS isp_name,
                c.country_code, cnt.country_name_en, cnt.country_name_ru, cnt.region,
                c.start_ip, c.end_ip, c.ip_count
            FROM cidr_blocks c
            LEFT JOIN providers p ON c.asn = p.asn
            LEFT JOIN countries cnt ON c.country_code = cnt.country_code
            WHERE c.ip_version = 6
        """)
        row = None
        for candidate in cur.fetchall():
            net = ipaddress.IPv6Network(candidate["cidr"], strict=False)
            if ip_obj in net:
                row = candidate
                break

    conn.close()
    if row:
        return dict(row)
    return {"message": "IP address not found in Ukraine / USA / Europe database."}

def search_providers(query, limit=20):
    conn = get_db()
    cur = conn.cursor()
    
    # Check if query is ASN number
    asn_query = None
    clean_q = query.strip().upper().replace("AS", "")
    if clean_q.isdigit():
        asn_query = int(clean_q)

    if asn_query:
        cur.execute("""
            SELECT asn, as_name, org_name, country_code, country_name_ru, region,
                   ipv4_cidr_count, ipv6_cidr_count, total_ipv4_ips
            FROM providers
            WHERE asn = ?
            LIMIT ?
        """, (asn_query, limit))
    else:
        pattern = f"%{query.strip()}%"
        cur.execute("""
            SELECT asn, as_name, org_name, country_code, country_name_ru, region,
                   ipv4_cidr_count, ipv6_cidr_count, total_ipv4_ips
            FROM providers
            WHERE org_name LIKE ? OR as_name LIKE ?
            ORDER BY total_ipv4_ips DESC
            LIMIT ?
        """, (pattern, pattern, limit))

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_cidrs(asn=None, country=None, region=None, ip_version=None, limit=1000):
    conn = get_db()
    cur = conn.cursor()

    conditions = []
    params = []

    if asn:
        conditions.append("c.asn = ?")
        params.append(asn)
    if country:
        conditions.append("c.country_code = ?")
        params.append(country.upper())
    if region:
        conditions.append("cnt.region = ?")
        params.append(region)
    if ip_version:
        conditions.append("c.ip_version = ?")
        params.append(int(ip_version))

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""
        SELECT 
            c.id, c.cidr, c.ip_version, c.asn,
            COALESCE(p.org_name, 'Unknown Provider') AS isp_name,
            c.country_code, cnt.country_name_en, cnt.country_name_ru, cnt.region,
            c.start_ip, c.end_ip, c.ip_count
        FROM cidr_blocks c
        LEFT JOIN providers p ON c.asn = p.asn
        LEFT JOIN countries cnt ON c.country_code = cnt.country_code
        {where_clause}
        ORDER BY c.ip_version, c.start_ip_int
    """
    if limit:
        query += f" LIMIT {int(limit)}"

    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_top_providers(country=None, region=None, limit=20):
    conn = get_db()
    cur = conn.cursor()

    conditions = []
    params = []

    if country:
        conditions.append("country_code = ?")
        params.append(country.upper())
    if region:
        conditions.append("region = ?")
        params.append(region)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""
        SELECT asn, as_name, org_name, country_code, country_name_ru, region,
               ipv4_cidr_count, ipv6_cidr_count, total_ipv4_ips
        FROM providers
        {where_clause}
        ORDER BY total_ipv4_ips DESC
        LIMIT ?
    """
    params.append(limit)
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_summary():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM regions ORDER BY total_ipv4_ips DESC")
    regions = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT country_code, country_name_en, country_name_ru, region,
               total_asns, total_v4_cidrs, total_v6_cidrs, total_cidrs, total_ipv4_ips
        FROM countries
        ORDER BY total_ipv4_ips DESC
    """)
    countries = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"regions": regions, "countries": countries}

def export_cidrs(asn=None, country=None, region=None, ip_version=None, fmt="txt", out_file=None):
    cidrs_data = get_cidrs(asn=asn, country=country, region=region, ip_version=ip_version, limit=None)
    output_lines = []

    list_name = "GEO_LIST"
    if country:
        list_name = f"ISP_{country.upper()}"
    elif asn:
        list_name = f"AS{asn}"
    elif region:
        list_name = f"REGION_{region.replace(' ', '_').upper()}"

    if fmt == "txt":
        for r in cidrs_data:
            output_lines.append(r["cidr"])
    elif fmt == "csv":
        output_lines.append("CIDR,IP_Version,ASN,ISP_Name,Country_Code,Country_Name,Start_IP,End_IP,IP_Count")
        for r in cidrs_data:
            name = r['isp_name'].replace('"', '""')
            output_lines.append(f'{r["cidr"]},{r["ip_version"]},{r["asn"]},"{name}",{r["country_code"]},{r["country_name_ru"]},{r["start_ip"]},{r["end_ip"]},{r["ip_count"] or ""}')
    elif fmt == "json":
        output_lines.append(json.dumps(cidrs_data, ensure_ascii=False, indent=2))
    elif fmt == "mikrotik":
        output_lines.append(f"# MikroTik RouterOS address-list script: {list_name}")
        output_lines.append("/ip firewall address-list")
        for r in cidrs_data:
            if r["ip_version"] == 4:
                comment = f"AS{r['asn']} {r['isp_name']}"[:50].replace('"', '')
                output_lines.append(f'add list="{list_name}" address={r["cidr"]} comment="{comment}"')
    elif fmt == "iptables":
        output_lines.append(f"# IPTables rules for {list_name}")
        for r in cidrs_data:
            if r["ip_version"] == 4:
                output_lines.append(f"iptables -A INPUT -s {r['cidr']} -j ACCEPT")
    elif fmt == "ipset":
        set_name = list_name.lower()[:30]
        output_lines.append(f"# IPSet configuration for {list_name}")
        output_lines.append(f"create {set_name} hash:net family inet hashsize 1024 maxelem 655360")
        for r in cidrs_data:
            if r["ip_version"] == 4:
                output_lines.append(f"add {set_name} {r['cidr']}")
    elif fmt == "nftables":
        set_name = list_name.lower()[:30]
        output_lines.append(f"# Nftables set definition for {list_name}")
        output_lines.append(f"table inet filter {{")
        output_lines.append(f"    set {set_name} {{")
        output_lines.append(f"        type ipv4_addr")
        output_lines.append(f"        flags interval")
        output_lines.append(f"        elements = {{")
        elements = [f"            {r['cidr']}" for r in cidrs_data if r["ip_version"] == 4]
        output_lines.append(",\n".join(elements))
        output_lines.append(f"        }}")
        output_lines.append(f"    }}")
        output_lines.append(f"}}")
    elif fmt == "nginx":
        output_lines.append(f"# Nginx geo / allow-block map for {list_name}")
        output_lines.append(f"geo $is_{list_name.lower()} {{")
        output_lines.append("    default 0;")
        for r in cidrs_data:
            output_lines.append(f"    {r['cidr']} 1;")
        output_lines.append("}")
    elif fmt == "cisco":
        output_lines.append(f"! Cisco IOS prefix-list for {list_name}")
        seq = 10
        for r in cidrs_data:
            output_lines.append(f"ip prefix-list {list_name} seq {seq} permit {r['cidr']}")
            seq += 10

    result_text = "\n".join(output_lines)
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(result_text)
        print(f"Exported {len(cidrs_data)} CIDRs to {out_file} (format: {fmt})")
    else:
        print(result_text)

def main():
    parser = argparse.ArgumentParser(description="ISP CIDR Database CLI Tool (Ukraine, USA, Europe)")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: lookup
    p_lookup = subparsers.add_parser("lookup", help="Lookup IP address details")
    p_lookup.add_argument("ip", help="IPv4 or IPv6 address to lookup")

    # Command: search
    p_search = subparsers.add_parser("search", help="Search ISP providers by name or ASN")
    p_search.add_argument("query", help="Provider name or ASN (e.g. Kyivstar, Comcast, AS15895)")
    p_search.add_argument("--limit", type=int, default=15, help="Max results")

    # Command: cidrs
    p_cidrs = subparsers.add_parser("cidrs", help="List CIDRs for ASN, country, or region")
    p_cidrs.add_argument("--asn", type=int, help="Autonomous System Number")
    p_cidrs.add_argument("--country", help="2-letter country code (UA, US, DE, FR, etc.)")
    p_cidrs.add_argument("--region", help="Region name (Ukraine, United States, Europe)")
    p_cidrs.add_argument("--ipv", choices=[4, 6], type=int, help="IP Version (4 or 6)")
    p_cidrs.add_argument("--limit", type=int, default=25, help="Max results to display")

    # Command: top
    p_top = subparsers.add_parser("top", help="Show top providers by allocated IPs")
    p_top.add_argument("--country", help="Filter by country (e.g. UA, US, DE)")
    p_top.add_argument("--region", help="Filter by region (Ukraine, United States, Europe)")
    p_top.add_argument("--limit", type=int, default=15, help="Number of results")

    # Command: stats
    subparsers.add_parser("stats", help="Show global statistics of the database")

    # Command: export
    p_export = subparsers.add_parser("export", help="Export CIDR list in various formats")
    p_export.add_argument("--asn", type=int, help="Filter by ASN")
    p_export.add_argument("--country", help="Filter by 2-letter country code (e.g. UA, US, DE)")
    p_export.add_argument("--region", help="Filter by region (Ukraine, United States, Europe)")
    p_export.add_argument("--ipv", choices=[4, 6], type=int, help="IP Version (4 or 6)")
    p_export.add_argument("--format", choices=["txt", "csv", "json", "mikrotik", "iptables", "ipset", "nftables", "nginx", "cisco"], default="txt")
    p_export.add_argument("--out", help="Output file path (prints to stdout if omitted)")

    args = parser.parse_args()

    if args.command == "lookup":
        res = ip_lookup(args.ip)
        if "error" in res:
            print("Error:", res["error"])
        elif "message" in res:
            print(res["message"])
        else:
            print(f"\n🔍 IP Lookup Result for: {args.ip}")
            print("=" * 55)
            print(f"CIDR Subnet:    {res['cidr']}")
            print(f"IP Version:     IPv{res['ip_version']}")
            print(f"ASN:            AS{res['asn']}")
            print(f"ISP / Provider: {res['isp_name']}")
            print(f"Country:        {res['country_name_ru']} ({res['country_code']})")
            print(f"Region:         {res['region']}")
            print(f"IP Range:       {res['start_ip']} - {res['end_ip']}")
            if res['ip_count']:
                print(f"Total IPs:      {res['ip_count']:,}")
            print("=" * 55)

    elif args.command == "search":
        results = search_providers(args.query, limit=args.limit)
        if not results:
            print(f"No providers found matching '{args.query}'.")
        else:
            print(f"\n🔎 Providers matching '{args.query}' (Found: {len(results)}):")
            print("=" * 80)
            print(f"{'ASN':<10} {'Country':<10} {'IPv4 CIDRs':<12} {'Total IPv4 IPs':<16} {'Provider Name'}")
            print("-" * 80)
            for r in results:
                ips = f"{r['total_ipv4_ips']:,}" if r['total_ipv4_ips'] else "0"
                print(f"AS{r['asn']:<8} {r['country_code']:<10} {r['ipv4_cidr_count']:<12} {ips:<16} {r['org_name'][:40]}")
            print("=" * 80)

    elif args.command == "cidrs":
        rows = get_cidrs(asn=args.asn, country=args.country, region=args.region, ip_version=args.ipv, limit=args.limit)
        print(f"\n📋 CIDR Blocks (Showing up to {args.limit}):")
        print("=" * 85)
        print(f"{'CIDR':<20} {'Ver':<5} {'ASN':<9} {'Country':<8} {'ISP / Organization'}")
        print("-" * 85)
        for r in rows:
            asn_str = f"AS{r['asn']}" if r['asn'] else "-"
            print(f"{r['cidr']:<20} IPv{r['ip_version']:<2} {asn_str:<9} {r['country_code']:<8} {r['isp_name'][:40]}")
        print("=" * 85)

    elif args.command == "top":
        results = get_top_providers(country=args.country, region=args.region, limit=args.limit)
        title = "TOP PROVIDERS"
        if args.country:
            title += f" IN {args.country.upper()}"
        elif args.region:
            title += f" IN {args.region.upper()}"
        print(f"\n🏆 {title} (Top {args.limit}):")
        print("=" * 80)
        print(f"{'ASN':<10} {'Country':<8} {'IPv4 CIDRs':<12} {'Total IPv4 IPs':<16} {'Provider Organization'}")
        print("-" * 80)
        for r in results:
            ips = f"{r['total_ipv4_ips']:,}" if r['total_ipv4_ips'] else "0"
            print(f"AS{r['asn']:<8} {r['country_code']:<8} {r['ipv4_cidr_count']:<12} {ips:<16} {r['org_name'][:40]}")
        print("=" * 80)

    elif args.command == "stats":
        data = get_summary()
        print("\n📊 ISP CIDR DATABASE OVERVIEW")
        print("=" * 80)
        print(f"{'Region':<16} {'Countries':<11} {'ASNs':<9} {'IPv4 CIDRs':<12} {'IPv6 CIDRs':<12} {'Total IPs'}")
        print("-" * 80)
        for reg in data["regions"]:
            ips = f"{reg['total_ipv4_ips']:,}"
            print(f"{reg['region']:<16} {reg['total_countries']:<11} {reg['total_asns']:<9} {reg['total_v4_cidrs']:<12} {reg['total_v6_cidrs']:<12} {ips}")
        print("=" * 80)
        print("\nTop 15 Countries by IPv4 Volume:")
        print(f"{'Code':<6} {'Country Name':<20} {'Region':<15} {'ASNs':<8} {'CIDRs':<10} {'Allocated IPv4'}")
        print("-" * 80)
        for c in data["countries"][:15]:
            ips = f"{c['total_ipv4_ips']:,}"
            print(f"{c['country_code']:<6} {c['country_name_ru']:<20} {c['region']:<15} {c['total_asns']:<8} {c['total_cidrs']:<10} {ips}")
        print("=" * 80)

    elif args.command == "export":
        export_cidrs(asn=args.asn, country=args.country, region=args.region, ip_version=args.ipv, fmt=args.format, out_file=args.out)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
