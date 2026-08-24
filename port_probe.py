#!/usr/bin/env python3
"""
Port Probe & SNMP Auditor
=========================
Checks additional management ports on known routers and performs a raw SNMPv1
GET (community "public"/"private") to read sysDescr — a classic way to confirm
device model and sometimes reveal credentials/config info.

Ports checked per router:
  TCP: 8291 (Winbox), 8728 (MikroTik API), 7547 (TR-069), 8080 (alt HTTP),
       8443 (alt HTTPS), 23 (Telnet), 22 (SSH)
  UDP: 161 (SNMP)

Results are stored in:
  * scan_routers.extra_ports  — JSON {port: "open"/"closed"/"filtered", ...}
  * device_ports table        — one row per open port
  * snmp_results table        — community -> sysDescr when readable

Usage:
    python3 port_probe.py [--limit N] [--tcp-only] [--snmp-only]
                          [--targets ip1,ip2] [--concurrency 50]
"""

import os
import sys
import json
import asyncio
import sqlite3
import argparse
import datetime
import struct

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(BASE_DIR, "isp_cidr.db"))

TCP_PORTS = [8291, 8728, 7547, 8080, 8443, 23, 22]
SNMP_COMMUNITIES = ["public", "private"]
SNMP_SYSDESCR_OID = "1.3.6.1.2.1.1.1.0"
SNMP_OIDS = {
    "sysDescr": "1.3.6.1.2.1.1.1.0",
    "sysName": "1.3.6.1.2.1.1.5.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "ifNumber": "1.3.6.1.2.1.2.1.0",
}

INIT_SQL = """
CREATE TABLE IF NOT EXISTS device_ports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL,
    port INTEGER NOT NULL,
    proto TEXT DEFAULT 'tcp',
    service TEXT,
    status TEXT,
    checked_at TEXT NOT NULL,
    UNIQUE(ip, port, proto)
);
CREATE TABLE IF NOT EXISTS snmp_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL,
    community TEXT,
    sys_descr TEXT,
    checked_at TEXT NOT NULL,
    UNIQUE(ip, community)
);
CREATE TABLE IF NOT EXISTS snmp_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL,
    community TEXT,
    oid TEXT,
    value TEXT,
    checked_at TEXT NOT NULL,
    UNIQUE(ip, community, oid)
);
"""


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_db(conn):
    cur = conn.cursor()
    cur.executescript(INIT_SQL)
    cols = [r[1] for r in cur.execute("PRAGMA table_info(scan_routers)")]
    if "extra_ports" not in cols:
        cur.execute("ALTER TABLE scan_routers ADD COLUMN extra_ports TEXT")
    conn.commit()


SERVICE_NAMES = {
    8291: "winbox", 8728: "mikrotik-api", 7547: "tr-069", 8080: "http-alt",
    8443: "https-alt", 23: "telnet", 22: "ssh", 161: "snmp",
}


async def tcp_probe(ip, port, timeout=2.5):
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return "open"
    except (asyncio.TimeoutError, OSError, ConnectionError):
        return "closed"
    except Exception:
        return "closed"


# ---------------------------------------------------------------------------
# Raw SNMPv1 GET (no external libs)
# ---------------------------------------------------------------------------
def snmp_oid_bytes(oid):
    parts = [int(x) for x in oid.split(".")]
    out = bytes([parts[0] * 40 + parts[1]])
    for p in parts[2:]:
        if p < 128:
            out += bytes([p])
        else:
            tmp = []
            while p:
                tmp.insert(0, p & 0x7F)
                p >>= 7
            for i, b in enumerate(tmp):
                if i < len(tmp) - 1:
                    b |= 0x80
                out += bytes([b])
    return out


def snmp_encode_length(n):
    if n < 128:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def snmp_tlv(tag, payload):
    return bytes([tag]) + snmp_encode_length(len(payload)) + payload


def snmp_build_get(community, oid, req_id=1):
    # version(0), community, PDU: get-request(0), req-id, error(0,0), varbind
    varbind = snmp_tlv(0x30, snmp_tlv(0x06, snmp_oid_bytes(oid)) + snmp_tlv(0x05, b""))
    varbinds = snmp_tlv(0x30, varbind)
    pdu = snmp_tlv(0xA0, snmp_tlv(0x02, req_id.to_bytes(4, "big"))
                   + snmp_tlv(0x02, b"\x00") + snmp_tlv(0x02, b"\x00") + varbinds)
    return snmp_tlv(0x30, snmp_tlv(0x02, b"\x01") + snmp_tlv(0x04, community.encode()) + pdu)


def snmp_parse_value(data):
    """Extract the value octets from a minimal SNMP response."""
    try:
        # walk to find the value after the OID; crude but works for sysDescr
        idx = data.find(b"\x30")
        # find OID TLV
        oid_idx = data.find(b"\x06")
        if oid_idx < 0:
            return None
        oid_len = data[oid_idx + 1]
        val_start = oid_idx + 2 + oid_len
        if val_start + 1 >= len(data):
            return None
        vtype = data[val_start]
        vlen = data[val_start + 1]
        if vlen & 0x80:
            nbytes = vlen & 0x7F
            vlen = int.from_bytes(data[val_start + 2: val_start + 2 + nbytes], "big")
            vstart = val_start + 2 + nbytes
        else:
            vstart = val_start + 2
        raw = data[vstart: vstart + vlen]
        if vtype == 0x04:  # OCTET STRING
            return raw.decode("utf-8", errors="ignore").strip()
        if vtype == 0x06:  # OID
            return raw.hex()
        if vtype == 0x02:  # INTEGER
            return str(int.from_bytes(raw, "big"))
        return raw.hex()
    except Exception:
        return None


class _SNMPProto(asyncio.DatagramProtocol):
    def __init__(self):
        self.queue = asyncio.Queue()

    def datagram_received(self, data, addr):
        self.queue.put_nowait(data)

    def error_received(self, exc):
        self.queue.put_nowait(b"")


async def snmp_get(ip, community, timeout=3.0, oid=SNMP_SYSDESCR_OID):
    """Raw SNMPv1 GET. Returns (value, error)."""
    try:
        loop = asyncio.get_event_loop()
        pkt = snmp_build_get(community, oid)
        transport, proto = await loop.create_datagram_endpoint(
            _SNMPProto, remote_addr=(ip, 161))
        transport.sendto(pkt)
        try:
            data = await asyncio.wait_for(proto.queue.get(), timeout=timeout)
            transport.close()
            if not data:
                return None, "no-response"
            val = snmp_parse_value(data)
            if val:
                return val, None
            return None, "no-value"
        except asyncio.TimeoutError:
            transport.close()
            return None, "timeout"
    except Exception as e:
        return None, str(e)[:60]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
async def probe_device(ip, tcp_only, snmp_only, timeout):
    result = {}
    if not snmp_only:
        for port in TCP_PORTS:
            st = await tcp_probe(ip, port, timeout)
            result[str(port)] = st
    if not tcp_only:
        for comm in SNMP_COMMUNITIES:
            for oid_name, oid in SNMP_OIDS.items():
                val, err = await snmp_get(ip, comm, timeout, oid)
                result[f"snmp:{comm}:{oid_name}"] = val if val else ("timeout" if err == "timeout" else "closed")
    return ip, result


async def run(ips, tcp_only, snmp_only, timeout, concurrency):
    sem = asyncio.Semaphore(concurrency)
    results = []
    total = len(ips)
    done = 0

    async def worker(ip):
        nonlocal done
        async with sem:
            ip, res = await probe_device(ip, tcp_only, snmp_only, timeout)
            results.append((ip, res))
            done += 1
            if done % 10 == 0 or done == total:
                print(f"  🔄 [{done}/{total}]")

    await asyncio.gather(*[worker(ip) for ip in ips])
    return results


def save(conn, results):
    cur = conn.cursor()
    now = get_now()
    for ip, res in results:
        open_ports = []
        for k, v in res.items():
            if k.startswith("snmp:"):
                parts = k.split(":")
                comm = parts[1]
                oid_name = parts[2] if len(parts) > 2 else "sysDescr"
                if v not in ("closed", "timeout", None):
                    if oid_name == "sysDescr":
                        cur.execute("INSERT OR REPLACE INTO snmp_results (ip, community, sys_descr, checked_at) VALUES (?,?,?,?)",
                                    (ip, comm, v, now))
                    cur.execute("INSERT OR REPLACE INTO snmp_data (ip, community, oid, value, checked_at) VALUES (?,?,?,?,?)",
                                (ip, comm, oid_name, v, now))
                continue
            port = int(k)
            if v == "open":
                open_ports.append(port)
                cur.execute("INSERT OR REPLACE INTO device_ports (ip, port, proto, service, status, checked_at) VALUES (?,?,?,?,?,?)",
                            (ip, port, "tcp", SERVICE_NAMES.get(port, ""), "open", now))
        cur.execute("UPDATE scan_routers SET extra_ports = ? WHERE ip = ?",
                    (json.dumps(open_ports), ip))
    conn.commit()
    return sum(1 for _, r in results for v in r.values() if v == "open")


def main():
    parser = argparse.ArgumentParser(description="Port probe & SNMP audit")
    parser.add_argument("--limit", type=int, help="Process only first N routers")
    parser.add_argument("--tcp-only", action="store_true")
    parser.add_argument("--snmp-only", action="store_true")
    parser.add_argument("--targets", help="Comma-separated IPs")
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=2.5)
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    cur = conn.cursor()

    if args.targets:
        ips = [x.strip() for x in args.targets.split(",") if x.strip()]
    else:
        sql = "SELECT ip FROM scan_routers ORDER BY id"
        if args.limit:
            sql += " LIMIT ?"
            ips = [r[0] for r in cur.execute(sql, (args.limit,)).fetchall()]
        else:
            ips = [r[0] for r in cur.execute(sql).fetchall()]
    conn.close()
    if not ips:
        print("Нет целей")
        return

    print(f"🔍 Целей: {len(ips)} (TCP:{'да' if not args.snmp_only else 'нет'}, SNMP:{'да' if not args.tcp_only else 'нет'})")
    import time as _t
    t0 = _t.time()
    results = asyncio.run(run(ips, args.tcp_only, args.snmp_only, args.timeout, args.concurrency))
    conn = sqlite3.connect(DB_PATH)
    open_n = save(conn, results)
    conn.close()
    print(f"✅ Готово за {_t.time()-t0:.1f}с | открытых доп. портов: {open_n}")


if __name__ == "__main__":
    main()
