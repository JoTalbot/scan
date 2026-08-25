#!/usr/bin/env python3
"""
ISP CIDR & IP Range Web Dashboard Server
Runs on 0.0.0.0:8000 and serves an interactive search, analytics, and export dashboard.
"""

import http.server
import socketserver
import json
import sqlite3
import urllib.parse
import os
import ipaddress

PORT = 8899
DB_PATH = os.path.join(os.path.dirname(__file__), "isp_cidr.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class ISPHandler(http.server.SimpleHTTPRequestHandler):
    def get_conn(self):
        return sqlite3.connect(DB_PATH)
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/api/stats":
            self.send_json(self.get_stats())
        elif path == "/api/lookup":
            ip = params.get("ip", [""])[0]
            self.send_json(self.lookup_ip(ip))
        elif path == "/api/search":
            q = params.get("q", [""])[0]
            country = params.get("country", [""])[0]
            region = params.get("region", [""])[0]
            ip_ver = params.get("ver", [""])[0]
            limit = int(params.get("limit", ["50"])[0])
            page = int(params.get("page", ["1"])[0])
            self.send_json(self.search_data(q, country, region, ip_ver, limit, page))
        elif path == "/api/top_providers":
            country = params.get("country", [""])[0]
            region = params.get("region", [""])[0]
            limit = int(params.get("limit", ["20"])[0])
            self.send_json(self.get_top(country, region, limit))
        elif path == "/api/export":
            country = params.get("country", [""])[0]
            region = params.get("region", [""])[0]
            asn = params.get("asn", [""])[0]
            fmt = params.get("format", ["txt"])[0]
            ip_ver = params.get("ver", [""])[0]
            self.handle_export(country, region, asn, fmt, ip_ver)
        elif path == "/api/routers":
            limit = int(params.get("limit", ["100"])[0])
            self.send_json(self.get_routers(limit))
        elif path == "/api/creds":
            self.send_json(self.get_creds())
        elif path == "/api/audit_stats":
            self.send_json(self.get_audit_stats())
        elif path == "/" or path == "/index.html":
            self.serve_html()
        else:
            super().do_GET()

    def get_routers(self, limit=100):
        conn = self.get_conn()
        cur = conn.cursor()
        rows = cur.execute("""
            SELECT ip, vendor, model, device_type, confidence, matched_on,
                   auth_result, browser_result, extra_ports
            FROM scan_routers
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return {"count": len(rows), "routers": [dict(zip(
            ["ip", "vendor", "model", "device_type", "confidence", "matched_on",
             "auth_result", "browser_result", "extra_ports"], r)) for r in rows]}

    def get_creds(self):
        conn = self.get_conn()
        cur = conn.cursor()
        rows = cur.execute("""
            SELECT ip, vendor, username, password, auth_method, http_status, checked_at
            FROM router_credentials ORDER BY id DESC LIMIT 200
        """).fetchall()
        conn.close()
        return {"count": len(rows), "creds": [dict(zip(
            ["ip", "vendor", "username", "password", "auth_method", "http_status", "checked_at"], r)) for r in rows]}

    def get_audit_stats(self):
        conn = self.get_conn()
        cur = conn.cursor()
        stats = {}
        for row in cur.execute("SELECT COALESCE(auth_result, 'not-checked') k, COUNT(*) c FROM scan_routers GROUP BY k ORDER BY c DESC"):
            stats["raw:" + row[0]] = row[1]
        for row in cur.execute("SELECT COALESCE(browser_result, 'not-checked') k, COUNT(*) c FROM scan_routers WHERE browser_checked=1 GROUP BY k ORDER BY c DESC"):
            stats["browser:" + row[0]] = row[1]
        try:
            stats["total_creds"] = cur.execute("SELECT COUNT(*) FROM router_credentials").fetchone()[0]
        except Exception:
            stats["total_creds"] = 0
        stats["total_routers"] = cur.execute("SELECT COUNT(*) FROM scan_routers").fetchone()[0]
        conn.close()
        return stats

    def send_json(self, data):
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def get_stats(self):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                region,
                COUNT(DISTINCT country_code) AS total_countries,
                SUM(total_asns) AS total_asns,
                SUM(total_v4_cidrs) AS total_v4_cidrs,
                SUM(total_v6_cidrs) AS total_v6_cidrs,
                SUM(total_cidrs) AS total_cidrs,
                SUM(total_ipv4_ips) AS total_ipv4_ips
            FROM countries
            GROUP BY region
            ORDER BY total_ipv4_ips DESC
        """)
        regions = [dict(r) for r in cur.fetchall()]
        cur.execute("""
            SELECT country_code, country_name_en, country_name_ru, region,
                   total_asns, total_v4_cidrs, total_v6_cidrs, total_cidrs, total_ipv4_ips
            FROM countries
            ORDER BY total_ipv4_ips DESC
        """)
        countries = [dict(r) for r in cur.fetchall()]
        
        cur.execute("SELECT COUNT(*) AS total_cidrs FROM cidr_blocks")
        tot_cidrs = cur.fetchone()["total_cidrs"]
        cur.execute("SELECT COUNT(*) AS total_asns FROM providers")
        tot_asns = cur.fetchone()["total_asns"]
        cur.execute("SELECT SUM(total_ipv4_ips) AS total_ips FROM countries")
        tot_ips = cur.fetchone()["total_ips"]

        conn.close()
        return {
            "total_cidrs": tot_cidrs,
            "total_asns": tot_asns,
            "total_ipv4_ips": tot_ips,
            "regions": regions,
            "countries": countries
        }

    def lookup_ip(self, ip_str):
        if not ip_str:
            return {"error": "No IP specified"}
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
                    id, cidr, ip_version, asn, isp_name,
                    country_code, country_name_en, country_name_ru, region,
                    start_ip, end_ip, netmask, wildcard_mask, ip_count
                FROM v_cidr_details
                WHERE ip_version = 4 AND start_ip_int <= ? AND end_ip_int >= ?
                ORDER BY (end_ip_int - start_ip_int) ASC
                LIMIT 1
            """, (ip_int, ip_int))
            row = cur.fetchone()
        else:
            cur.execute("""
                SELECT 
                    id, cidr, ip_version, asn, isp_name,
                    country_code, country_name_en, country_name_ru, region,
                    start_ip, end_ip, netmask, wildcard_mask, ip_count
                FROM v_cidr_details
                WHERE ip_version = 6
            """)
            row = None
            for candidate in cur.fetchall():
                net = ipaddress.IPv6Network(candidate["cidr"], strict=False)
                if ip_obj in net:
                    row = candidate
                    break

        conn.close()
        if row:
            return {"found": True, "data": dict(row)}
        return {"found": False, "message": "IP not found in Ukraine / USA / Europe database"}

    def search_data(self, q, country, region, ip_ver, limit=50, page=1):
        conn = get_db()
        cur = conn.cursor()
        
        offset = (page - 1) * limit
        conditions = []
        params = []

        if country:
            conditions.append("country_code = ?")
            params.append(country.upper())
        if region:
            conditions.append("region = ?")
            params.append(region)
        if ip_ver in ["4", "6"]:
            conditions.append("ip_version = ?")
            params.append(int(ip_ver))

        if q:
            clean_asn = q.upper().replace("AS", "").strip()
            if clean_asn.isdigit():
                conditions.append("(asn = ? OR cidr LIKE ?)")
                params.extend([int(clean_asn), f"%{q.strip()}%"])
            else:
                conditions.append("(isp_name LIKE ? OR cidr LIKE ? OR country_name_ru LIKE ? OR start_ip LIKE ?)")
                pat = f"%{q.strip()}%"
                params.extend([pat, pat, pat, pat])

        where = " WHERE " + " AND ".join(conditions) if conditions else ""

        cur.execute(f"SELECT COUNT(*) as count FROM v_cidr_details {where}", params)
        total_count = cur.fetchone()["count"]

        query = f"""
            SELECT 
                id, cidr, ip_version, asn, isp_name,
                country_code, country_name_en, country_name_ru, region,
                start_ip, end_ip, netmask, wildcard_mask, ip_count
            FROM v_cidr_details
            {where}
            ORDER BY ip_version, start_ip_int
            LIMIT ? OFFSET ?
        """
        cur.execute(query, params + [limit, offset])
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {
            "total": total_count,
            "page": page,
            "limit": limit,
            "pages": (total_count + limit - 1) // limit,
            "results": rows
        }

    def get_top(self, country, region, limit=20):
        conn = get_db()
        cur = conn.cursor()
        conds = []
        params = []
        if country:
            conds.append("country_code = ?")
            params.append(country.upper())
        if region:
            conds.append("region = ?")
            params.append(region)
        where = " WHERE " + " AND ".join(conds) if conds else ""
        cur.execute(f"""
            SELECT asn, as_name, org_name, country_code, country_name_ru, region,
                   ipv4_cidr_count, ipv6_cidr_count, total_ipv4_ips
            FROM providers
            {where}
            ORDER BY total_ipv4_ips DESC
            LIMIT ?
        """, params + [limit])
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def handle_export(self, country, region, asn, fmt, ip_ver):
        conn = get_db()
        cur = conn.cursor()
        conds = []
        params = []
        if country:
            conds.append("country_code = ?")
            params.append(country.upper())
        if region:
            conds.append("region = ?")
            params.append(region)
        if asn and asn.isdigit():
            conds.append("asn = ?")
            params.append(int(asn))
        if ip_ver in ["4", "6"]:
            conds.append("ip_version = ?")
            params.append(int(ip_ver))
        where = " WHERE " + " AND ".join(conds) if conds else ""

        cur.execute(f"""
            SELECT cidr, ip_version, asn, isp_name,
                   country_code, country_name_ru, start_ip, end_ip, netmask, wildcard_mask, ip_count
            FROM v_cidr_details
            {where}
            ORDER BY ip_version, start_ip_int
        """, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        tag = country or (f"AS{asn}" if asn else (region or "ALL"))
        filename = f"cidr_export_{tag}.{fmt if fmt in ['csv', 'json', 'txt'] else 'txt'}"

        if fmt == "csv":
            mime = "text/csv; charset=utf-8"
            out = "CIDR,IP_Version,Start_IP,End_IP,Netmask,Wildcard_Mask,Total_IPs,ASN,ISP_Name,Country_Code,Country_Name\n"
            for r in rows:
                name = (r['isp_name'] or "").replace('"', '""')
                out += f'{r["cidr"]},{r["ip_version"]},{r["start_ip"]},{r["end_ip"]},{r["netmask"] or ""},{r["wildcard_mask"] or ""},{r["ip_count"] or ""},{r["asn"]},"{name}",{r["country_code"]},{r["country_name_ru"]}\n'
        elif fmt == "ranges":
            mime = "text/plain; charset=utf-8"
            out = "\n".join(f"{r['start_ip']} - {r['end_ip']}\tAS{r['asn']}\t{r['isp_name']}" for r in rows)
        elif fmt == "json":
            mime = "application/json; charset=utf-8"
            out = json.dumps(rows, ensure_ascii=False, indent=2)
        elif fmt == "mikrotik":
            mime = "text/plain; charset=utf-8"
            out = f"# MikroTik Address List: {tag}\n/ip firewall address-list\n"
            for r in rows:
                if r["ip_version"] == 4:
                    c = f"AS{r['asn']} {r['isp_name']}"[:45].replace('"', '')
                    out += f'add list="{tag}" address={r["cidr"]} comment="{c}"\n'
        elif fmt == "iptables":
            mime = "text/plain; charset=utf-8"
            out = f"# IPTables rules for {tag}\n"
            for r in rows:
                if r["ip_version"] == 4:
                    out += f"iptables -A INPUT -s {r['cidr']} -j ACCEPT\n"
        elif fmt == "nginx":
            mime = "text/plain; charset=utf-8"
            out = f"# Nginx Geo config for {tag}\ngeo $is_{tag.lower()} {{\n    default 0;\n"
            for r in rows:
                out += f"    {r['cidr']} 1;\n"
            out += "}\n"
        else:
            mime = "text/plain; charset=utf-8"
            out = "\n".join(r["cidr"] for r in rows)

        content = out.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def serve_html(self):
        html_code = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>База данных CIDR и диапазонов IP провайдеров (Украина, США, Европа)</title>
<style>
  :root {
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --accent: #58a6ff;
    --accent-glow: rgba(88, 166, 255, 0.15);
    --text: #c9d1d9;
    --text-bright: #f0f6fc;
    --text-muted: #8b949e;
    --green: #3fb950;
    --yellow: #d29922;
    --purple: #bc8cff;
    --red: #f85149;
    --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-sans);
    line-height: 1.5;
    padding-bottom: 60px;
  }
  .container { max-width: 1400px; margin: 0 auto; padding: 24px; }
  
  /* Header */
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
    flex-wrap: wrap;
    gap: 16px;
  }
  .title-group h1 {
    font-size: 26px;
    font-weight: 700;
    color: var(--text-bright);
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .title-group p { color: var(--text-muted); font-size: 14px; margin-top: 4px; }
  .badge-tag {
    background: #1f6feb22;
    color: var(--accent);
    border: 1px solid #388bfd44;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-family: var(--font-mono);
  }

  /* Stats Grid */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    margin-bottom: 28px;
  }
  .stat-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px;
    transition: transform 0.15s, border-color 0.15s;
  }
  .stat-card:hover { border-color: var(--accent); transform: translateY(-2px); }
  .stat-title { font-size: 12px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px; font-weight: 600; }
  .stat-val { font-size: 26px; font-weight: 700; color: var(--text-bright); margin: 6px 0 2px; }
  .stat-sub { font-size: 12px; color: var(--text-muted); }

  /* IP Lookup Widget */
  .lookup-section {
    background: linear-gradient(135deg, #161b22, #1c2128);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 22px;
    margin-bottom: 28px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  }
  .lookup-box {
    display: flex;
    gap: 12px;
    margin-top: 14px;
    flex-wrap: wrap;
  }
  input, select, button {
    background: #0d1117;
    border: 1px solid var(--border);
    color: var(--text-bright);
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 14px;
    outline: none;
    font-family: inherit;
  }
  input:focus, select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-glow); }
  input[type="text"] { flex: 1; min-width: 260px; font-family: var(--font-mono); }
  .btn {
    background: #238636;
    color: #fff;
    border: none;
    font-weight: 600;
    cursor: pointer;
    padding: 10px 20px;
    border-radius: 6px;
    transition: background 0.15s;
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .btn:hover { background: #2ea043; }
  .btn-secondary {
    background: #21262d;
    color: var(--text-bright);
    border: 1px solid var(--border);
  }
  .btn-secondary:hover { background: #30363d; border-color: #8b949e; }
  .lookup-result {
    margin-top: 16px;
    padding: 16px;
    border-radius: 8px;
    background: #0d1117;
    border: 1px solid var(--border);
    display: none;
  }
  .lookup-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
  }
  .res-item { display: flex; flex-direction: column; }
  .res-lbl { font-size: 11px; color: var(--text-muted); text-transform: uppercase; }
  .res-val { font-size: 14px; color: var(--text-bright); font-weight: 600; font-family: var(--font-mono); margin-top: 2px; }

  /* Main Area Tabs & Filters */
  .section-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 28px;
  }
  .filters-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: 18px;
  }
  .quick-filters {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .pill {
    padding: 6px 12px;
    background: #21262d;
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 20px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s;
  }
  .pill:hover, .pill.active {
    background: #1f6feb;
    border-color: #58a6ff;
    color: #fff;
  }

  /* Table styling */
  .table-wrap { overflow-x: auto; margin-top: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
  th {
    background: #0d1117;
    color: var(--text-muted);
    font-weight: 600;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
  }
  td {
    padding: 10px 12px;
    border-bottom: 1px solid #21262d;
    color: var(--text);
  }
  tr:hover td { background: rgba(88, 166, 255, 0.04); }
  .font-mono { font-family: var(--font-mono); }
  .tag-asn {
    background: #1f6feb22;
    color: #79c0ff;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
  }
  .tag-v4 { background: rgba(63, 185, 80, 0.15); color: #7ee787; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
  .tag-v6 { background: rgba(188, 140, 255, 0.15); color: #d2a8ff; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
  .tag-country {
    background: #21262d;
    border: 1px solid var(--border);
    color: var(--text-bright);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
  }

  /* Pagination */
  .pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 16px;
    font-size: 13px;
    color: var(--text-muted);
    flex-wrap: wrap;
    gap: 10px;
  }
  .page-btns { display: flex; gap: 8px; }

  /* Export modal / bar */
  .export-panel {
    background: #0d1117;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-top: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
  }
  .export-controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }

  /* Two column top providers & countries */
  .grid-2col {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
    gap: 20px;
    margin-bottom: 28px;
  }
  .badge-count {
    background: #30363d;
    color: #f0f6fc;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 12px;
  }
</style>
</head>
<body>

<div class="container">
  <header>
    <div class="title-group">
      <h1>🌐 База Данных CIDR и Диапазонов IP</h1>
      <p>Официальные пулы IP-адресов, автономные системы (ASN), диапазоны от начального до конечного IP и маски подсетей (Украина, США, Европа)</p>
    </div>
    <div>
      <span class="badge-tag">RIPE NCC + ARIN</span>
      <span class="badge-tag">508,879 CIDRs</span>
      <span class="badge-tag">508,879 IP Ranges</span>
    </div>
  </header>

  <!-- Overview Stats -->
  <div class="stats-grid" id="statsGrid">
    <div class="stat-card">
      <div class="stat-title">Всего CIDR & Диапазонов</div>
      <div class="stat-val" id="stTotalCidrs">508,879</div>
      <div class="stat-sub">385k IPv4 / 123k IPv6</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">Украина (UA)</div>
      <div class="stat-val" style="color: #58a6ff;" id="stUaCidrs">6,838</div>
      <div class="stat-sub">1,592 ASN • 8,258,301 IPv4 адресов</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">Европа (49 стран)</div>
      <div class="stat-val" style="color: #7ee787;" id="stEuCidrs">181,264</div>
      <div class="stat-sub">20,471 ASN • 561.8M IPv4 адресов</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">США (USA)</div>
      <div class="stat-val" style="color: #d2a8ff;" id="stUsCidrs">320,777</div>
      <div class="stat-sub">18,587 ASN • 1.35B IPv4 адресов</div>
    </div>
  </div>

  <!-- Instant IP Lookup Section -->
  <div class="lookup-section">
    <h3 style="color: var(--text-bright); font-size: 16px; margin-bottom: 4px;">🔍 Мгновенный поиск диапазона по IP адресу</h3>
    <p style="font-size: 13px; color: var(--text-muted);">Введите любой IPv4 или IPv6 адрес, чтобы узнать начальный/конечный IP, маску, CIDR, ASN и интернет-провайдера</p>
    
    <div class="lookup-box">
      <input type="text" id="ipInput" placeholder="Например: 5.248.10.20, 195.138.64.1, 8.8.8.8, 88.198.50.1, 2001:678:c8::1" />
      <button class="btn" onclick="doLookup()">Проверить IP</button>
      <button class="btn btn-secondary" onclick="demoLookup('5.248.10.20')">Киевстар UA</button>
      <button class="btn btn-secondary" onclick="demoLookup('195.138.64.1')">TENET UA</button>
      <button class="btn btn-secondary" onclick="demoLookup('88.198.50.1')">Hetzner DE</button>
      <button class="btn btn-secondary" onclick="demoLookup('8.8.8.8')">Google US</button>
    </div>

    <div class="lookup-result" id="lookupResult"></div>
  </div>

  <!-- Main Database Explorer -->
  <div class="section-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
      <h3 style="color: var(--text-bright); font-size: 18px;">📋 Обозреватель CIDR и Диапазонов IP (Таблицы cidr_blocks & ip_ranges)</h3>
      <div class="quick-filters">
        <button class="pill active" onclick="setRegionFilter('', this)">Все регионы</button>
        <button class="pill" onclick="setCountryFilter('UA', this)">🇺🇦 Украина</button>
        <button class="pill" onclick="setCountryFilter('US', this)">🇺🇸 США</button>
        <button class="pill" onclick="setCountryFilter('DE', this)">🇩🇪 Германия</button>
        <button class="pill" onclick="setCountryFilter('FR', this)">🇫🇷 Франция</button>
        <button class="pill" onclick="setCountryFilter('GB', this)">🇬🇧 Великобритания</button>
        <button class="pill" onclick="setCountryFilter('PL', this)">🇵🇱 Польша</button>
        <button class="pill" onclick="setCountryFilter('NL', this)">🇳🇱 Нидерланды</button>
        <button class="pill" onclick="setRegionFilter('Europe', this)">🇪🇺 Вся Европа</button>
      </div>
    </div>

    <!-- Filters Row -->
    <div class="filters-row">
      <input type="text" id="searchQuery" placeholder="Поиск по названию (Kyivstar, Vodafone, Hetzner, Comcast), ASN (15895) или начальному IP..." oninput="debounceSearch()" style="min-width: 320px;" />
      
      <select id="countrySelect" onchange="runSearch()">
        <option value="">Все страны</option>
        <option value="UA">Украина (UA)</option>
        <option value="US">США (US)</option>
        <option value="DE">Германия (DE)</option>
        <option value="GB">Великобритания (GB)</option>
        <option value="FR">Франция (FR)</option>
        <option value="NL">Нидерланды (NL)</option>
        <option value="IT">Италия (IT)</option>
        <option value="ES">Испания (ES)</option>
        <option value="PL">Польша (PL)</option>
        <option value="SE">Швеция (SE)</option>
        <option value="CH">Швейцария (CH)</option>
        <option value="AT">Австрия (AT)</option>
        <option value="NO">Норвегия (NO)</option>
        <option value="CZ">Чехия (CZ)</option>
        <option value="RO">Румыния (RO)</option>
      </select>

      <select id="versionSelect" onchange="runSearch()">
        <option value="">IPv4 & IPv6</option>
        <option value="4">Только IPv4</option>
        <option value="6">Только IPv6</option>
      </select>

      <button class="btn btn-secondary" onclick="resetFilters()">Сброс</button>
    </div>

    <!-- Table -->
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>CIDR</th>
            <th>Начальный IP</th>
            <th>Конечный IP</th>
            <th>Маска</th>
            <th>ASN</th>
            <th>Интернет-провайдер</th>
            <th>Страна</th>
            <th>Количество IP</th>
          </tr>
        </thead>
        <tbody id="cidrTableBody">
          <tr><td colspan="8" style="text-align: center; padding: 30px; color: var(--text-muted);">Загрузка данных...</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination & Stats -->
    <div class="pagination">
      <div id="pageInfo">Показано 0 из 0</div>
      <div class="page-btns">
        <button class="btn btn-secondary" id="btnPrev" onclick="changePage(-1)">← Назад</button>
        <span id="curPageNum" style="display: flex; align-items: center; padding: 0 10px; font-weight: 600;">1 / 1</span>
        <button class="btn btn-secondary" id="btnNext" onclick="changePage(1)">Вперед →</button>
      </div>
    </div>

    <!-- Export Panel -->
    <div class="export-panel">
      <div>
        <div style="font-weight: 600; color: var(--text-bright); font-size: 14px;">Экспорт диапазонов и CIDR текущей выборки:</div>
        <div style="font-size: 12px; color: var(--text-muted);">Скачивание готовых файлов и правил для фаерволов и маршрутизаторов</div>
      </div>
      <div class="export-controls">
        <select id="exportFormat">
          <option value="txt">Список CIDR (.txt)</option>
          <option value="ranges">Диапазоны Start-End (.txt)</option>
          <option value="csv">Таблица с масками (.csv)</option>
          <option value="json">Данные JSON (.json)</option>
          <option value="mikrotik">MikroTik RouterOS Script (.rsc)</option>
          <option value="iptables">Linux IPTables Rules (.sh)</option>
          <option value="nginx">Nginx Geo Block (.conf)</option>
        </select>
        <button class="btn" onclick="doExport()">📥 Скачать экспорт</button>
      </div>
    </div>
  </div>

  <!-- 2 Column Section: Top Ukraine Providers & Top European Countries -->
  <div class="grid-2col">
    <!-- Top Ukraine Providers -->
    <div class="section-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 style="color: var(--text-bright); font-size: 16px;">🇺🇦 Топ провайдеров Украины</h3>
        <span class="badge-count">по числу IPv4</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ASN</th>
              <th>Провайдер</th>
              <th>CIDR</th>
              <th>Всего IPv4</th>
            </tr>
          </thead>
          <tbody id="topUaBody"></tbody>
        </table>
      </div>
    </div>

    <!-- Top Countries Leaderboard -->
    <div class="section-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 style="color: var(--text-bright); font-size: 16px;">🏆 Рейтинг стран по объему IP</h3>
        <span class="badge-count">Европа, США, Украина</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Страна</th>
              <th>Регион</th>
              <th>ASN</th>
              <th>CIDR</th>
              <th>IPv4 емкость</th>
            </tr>
          </thead>
          <tbody id="topCountriesBody"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
let currentPage = 1;
let currentLimit = 25;
let currentRegion = '';
let currentCountry = '';
let debounceTimer = null;

async function init() {
  loadStats();
  runSearch();
  loadTopUa();
  loadTopCountries();
  loadRouters();
  loadAuditStats();
}

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('stTotalCidrs').textContent = Number(data.total_cidrs).toLocaleString();
    
    const ua = data.countries.find(c => c.country_code === 'UA');
    if (ua) {
      document.getElementById('stUaCidrs').textContent = Number(ua.total_cidrs).toLocaleString();
    }
    const eu = data.regions.find(r => r.region === 'Europe');
    if (eu) {
      document.getElementById('stEuCidrs').textContent = Number(eu.total_cidrs).toLocaleString();
    }
    const us = data.countries.find(c => c.country_code === 'US');
    if (us) {
      document.getElementById('stUsCidrs').textContent = Number(us.total_cidrs).toLocaleString();
    }
  } catch (e) {
    console.error(e);
  }
}

async function runSearch() {
  const q = document.getElementById('searchQuery').value;
  const country = currentCountry || document.getElementById('countrySelect').value;
  const ver = document.getElementById('versionSelect').value;

  const url = `/api/search?q=${encodeURIComponent(q)}&country=${encodeURIComponent(country)}&region=${encodeURIComponent(currentRegion)}&ver=${encodeURIComponent(ver)}&limit=${currentLimit}&page=${currentPage}`;
  
  try {
    const res = await fetch(url);
    const data = await res.json();
    renderTable(data);
  } catch (e) {
    console.error(e);
  }
}

function renderTable(data) {
  const tbody = document.getElementById('cidrTableBody');
  if (!data.results || data.results.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 24px; color: var(--text-muted);">Ничего не найдено по заданным фильтрам.</td></tr>';
    document.getElementById('pageInfo').textContent = 'Найдено: 0';
    document.getElementById('curPageNum').textContent = '1 / 1';
    return;
  }

  let html = '';
  for (const r of data.results) {
    const asnBadge = r.asn ? `<span class="tag-asn" style="cursor:pointer" onclick="filterByAsn(${r.asn})">AS${r.asn}</span>` : '-';
    const ipsCount = r.ip_count ? Number(r.ip_count).toLocaleString() : (r.ip_version === 6 ? 'IPv6 блок' : '-');
    const maskStr = r.netmask ? `<span class="font-mono" style="font-size:11px; color: var(--text-muted);">${r.netmask}</span>` : '-';

    html += `<tr>
      <td class="font-mono" style="font-weight:600; color: var(--accent);">${r.cidr}</td>
      <td class="font-mono" style="color: var(--text-bright);">${r.start_ip}</td>
      <td class="font-mono" style="color: var(--text-bright);">${r.end_ip}</td>
      <td>${maskStr}</td>
      <td>${asnBadge}</td>
      <td style="color: var(--text-bright);">${escapeHtml(r.isp_name)}</td>
      <td><span class="tag-country">${r.country_code}</span> ${r.country_name_ru}</td>
      <td class="font-mono">${ipsCount}</td>
    </tr>`;
  }
  tbody.innerHTML = html;

  const start = (data.page - 1) * data.limit + 1;
  const end = Math.min(data.page * data.limit, data.total);
  document.getElementById('pageInfo').textContent = `Показано ${start.toLocaleString()} - ${end.toLocaleString()} из ${Number(data.total).toLocaleString()}`;
  document.getElementById('curPageNum').textContent = `${data.page} / ${Math.max(1, data.pages)}`;
  document.getElementById('btnPrev').disabled = (data.page <= 1);
  document.getElementById('btnNext').disabled = (data.page >= data.pages);
}

function debounceSearch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    currentPage = 1;
    runSearch();
  }, 250);
}

function changePage(delta) {
  currentPage += delta;
  if (currentPage < 1) currentPage = 1;
  runSearch();
}

function setCountryFilter(cc, btn) {
  currentCountry = cc;
  currentRegion = '';
  document.getElementById('countrySelect').value = cc;
  updatePills(btn);
  currentPage = 1;
  runSearch();
}

function setRegionFilter(reg, btn) {
  currentRegion = reg;
  currentCountry = '';
  document.getElementById('countrySelect').value = '';
  updatePills(btn);
  currentPage = 1;
  runSearch();
}

function filterByAsn(asn) {
  document.getElementById('searchQuery').value = 'AS' + asn;
  currentPage = 1;
  runSearch();
}

function resetFilters() {
  document.getElementById('searchQuery').value = '';
  document.getElementById('countrySelect').value = '';
  document.getElementById('versionSelect').value = '';
  currentCountry = '';
  currentRegion = '';
  currentPage = 1;
  const firstPill = document.querySelector('.quick-filters .pill');
  if (firstPill) updatePills(firstPill);
  runSearch();
}

function updatePills(activeBtn) {
  document.querySelectorAll('.quick-filters .pill').forEach(p => p.classList.remove('active'));
  if (activeBtn) activeBtn.classList.add('active');
}

async function doLookup() {
  const ip = document.getElementById('ipInput').value.trim();
  if (!ip) return;

  const resDiv = document.getElementById('lookupResult');
  resDiv.style.display = 'block';
  resDiv.innerHTML = '<span style="color: var(--text-muted);">Проверка в базе данных...</span>';

  try {
    const res = await fetch(`/api/lookup?ip=${encodeURIComponent(ip)}`);
    const data = await res.json();
    
    if (data.found && data.data) {
      const d = data.data;
      resDiv.innerHTML = `
        <div class="lookup-grid">
          <div class="res-item">
            <span class="res-lbl">CIDR Подсеть</span>
            <span class="res-val" style="color: #58a6ff;">${d.cidr} (IPv${d.ip_version})</span>
          </div>
          <div class="res-item">
            <span class="res-lbl">Диапазон IP (Start - End)</span>
            <span class="res-val" style="color: #7ee787;">${d.start_ip} - ${d.end_ip}</span>
          </div>
          <div class="res-item">
            <span class="res-lbl">Сетевая маска (Netmask)</span>
            <span class="res-val">${d.netmask || '-'} (Wildcard: ${d.wildcard_mask || '-'})</span>
          </div>
          <div class="res-item">
            <span class="res-lbl">Автономная система</span>
            <span class="res-val" style="color: #bc8cff;">AS${d.asn}</span>
          </div>
          <div class="res-item">
            <span class="res-lbl">Провайдер / ISP</span>
            <span class="res-val" style="color: #f0f6fc;">${escapeHtml(d.isp_name)}</span>
          </div>
          <div class="res-item">
            <span class="res-lbl">Страна / Регион</span>
            <span class="res-val" style="color: #3fb950;">${d.country_name_ru} (${d.country_code}) • ${d.region}</span>
          </div>
          <div class="res-item">
            <span class="res-lbl">Емкость подсети</span>
            <span class="res-val">${d.ip_count ? Number(d.ip_count).toLocaleString() + ' IPs' : 'IPv6'}</span>
          </div>
        </div>
      `;
    } else {
      resDiv.innerHTML = `<span style="color: var(--yellow);">⚠️ ${data.message || data.error}</span>`;
    }
  } catch (e) {
    resDiv.innerHTML = `<span style="color: var(--red);">Ошибка соединения: ${e}</span>`;
  }
}

function demoLookup(ip) {
  document.getElementById('ipInput').value = ip;
  doLookup();
}

async function loadTopUa() {
  try {
    const res = await fetch('/api/top_providers?country=UA&limit=8');
    const data = await res.json();
    const tbody = document.getElementById('topUaBody');
    let html = '';
    for (const r of data) {
      html += `<tr>
        <td><span class="tag-asn" style="cursor:pointer" onclick="filterByAsn(${r.asn})">AS${r.asn}</span></td>
        <td style="color: var(--text-bright);">${escapeHtml(r.org_name)}</td>
        <td class="font-mono">${r.ipv4_cidr_count}</td>
        <td class="font-mono" style="font-weight:600; color: #58a6ff;">${Number(r.total_ipv4_ips).toLocaleString()}</td>
      </tr>`;
    }
    tbody.innerHTML = html;
  } catch (e) { console.error(e); }
}

async function loadTopCountries() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    const tbody = document.getElementById('topCountriesBody');
    let html = '';
    for (const c of data.countries.slice(0, 8)) {
      html += `<tr>
        <td><span class="tag-country">${c.country_code}</span> ${c.country_name_ru}</td>
        <td style="font-size:12px; color: var(--text-muted);">${c.region}</td>
        <td class="font-mono">${Number(c.total_asns).toLocaleString()}</td>
        <td class="font-mono">${Number(c.total_cidrs).toLocaleString()}</td>
        <td class="font-mono" style="font-weight:600; color: #7ee787;">${Number(c.total_ipv4_ips).toLocaleString()}</td>
      </tr>`;
    }
    tbody.innerHTML = html;
  } catch (e) { console.error(e); }
}

function doExport() {
  const country = currentCountry || document.getElementById('countrySelect').value;
  const ver = document.getElementById('versionSelect').value;
  const fmt = document.getElementById('exportFormat').value;
  const q = document.getElementById('searchQuery').value.trim();
  
  let asn = '';
  if (q.toUpperCase().startsWith('AS') && !isNaN(q.substring(2))) {
    asn = q.substring(2);
  }

  const url = `/api/export?country=${encodeURIComponent(country)}&region=${encodeURIComponent(currentRegion)}&asn=${encodeURIComponent(asn)}&ver=${encodeURIComponent(ver)}&format=${fmt}`;
  window.open(url, '_blank');
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ===== Роутеры и аудит =====
async function loadRouters() {
  try {
    const res = await fetch('/api/routers?limit=30');
    const data = await res.json();
    const tb = document.getElementById('routerTable');
    if (!tb) return;
    tb.innerHTML = '';
    document.getElementById('routerCount').textContent = data.count + ' показано';
    data.routers.forEach(r => {
      const tr = document.createElement('tr');
      const st = r.auth_result || r.browser_result || 'not-checked';
      tr.innerHTML = `<td>${esc(r.ip)}</td><td>${esc(r.vendor || '-')}</td><td>${esc(r.model || '-')}</td>
        <td>${esc(r.device_type || '-')}</td><td>${esc(st)}</td><td>${esc(r.extra_ports || '')}</td>`;
      tb.appendChild(tr);
    });
  } catch (e) { console.log('routers err', e); }
}

async function loadAuditStats() {
  try {
    const res = await fetch('/api/audit_stats');
    const d = await res.json();
    const el = document.getElementById('auditStats');
    if (!el) return;
    let html = `<b>Роутеров всего: ${d.total_routers || 0}</b> | Пар: ${d.total_creds || 0}<br>`;
    for (const [k, v] of Object.entries(d)) {
      if (k.startsWith('raw:') || k.startsWith('browser:')) html += `<span class="badge-tag">${esc(k)}: ${v}</span> `;
    }
    el.innerHTML = html;
  } catch (e) { console.log('audit err', e); }
}

window.onload = init;
</script>

  <!-- Router Audit Section -->
  <div class="section" style="margin-top:24px;">
    <h2>🛜 Обнаруженные роутеры <span id="routerCount" style="font-size:14px;color:#8b949e;"></span></h2>
    <div id="auditStats" style="margin-bottom:12px;"></div>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead><tr style="color:#58a6ff;text-align:left;">
        <th style="padding:6px;">IP</th><th>Вендор</th><th>Модель</th><th>Тип</th><th>Статус аудита</th><th>Доп. порты</th>
      </tr></thead>
      <tbody id="routerTable"></tbody>
    </table>
  </div>

</body>
</html>
"""
        content = html_code.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

def run():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), ISPHandler) as httpd:
        print(f"ISP CIDR Dashboard web server running at http://0.0.0.0:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run()
