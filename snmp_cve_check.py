#!/usr/bin/env python3
"""
SNMP CVE check for affected routers
===================================
Читает IP-адреса из docs/CVE_PRIORITY.md (раздел CVE-2022-45315, MikroTik
SNMP OOB read → RCE) и для каждого IP проверяет доступность SNMP (UDP 161)
с community-строками public/private.

Реализация SNMPv1 GetRequest полностью на socket (BER-кодирование вручную),
без внешних библиотек.

Usage:
    python3 snmp_cve_check.py
    python3 snmp_cve_check.py --file docs/CVE_PRIORITY.md --timeout 2.0
    python3 snmp_cve_check.py --communities public,private
"""

import os
import re
import sys
import socket
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CVE_ID = "CVE-2022-45315"
DEFAULT_FILE = os.path.join(BASE_DIR, "docs", "CVE_PRIORITY.md")
SNMP_PORT = 161
SYS_DESCR_OID = (1, 3, 6, 1, 2, 1, 1, 1, 0)  # 1.3.6.1.2.1.1.1.0


# ---------------------------------------------------------------------------
# Минимальный BER/DER энкодер для SNMPv1 (только нужные типы)
# ---------------------------------------------------------------------------
def ber_len(n):
    if n < 0x80:
        return bytes([n])
    raw = []
    while n:
        raw.insert(0, n & 0xFF)
        n >>= 8
    return bytes([0x80 | len(raw)] + raw)


def ber_tlv(tag, content):
    return bytes([tag]) + ber_len(len(content)) + bytes(content)


def ber_int(value):
    raw = []
    while True:
        raw.insert(0, value & 0xFF)
        value >>= 8
        if value == 0:
            break
    if raw[0] & 0x80:
        raw.insert(0, 0)
    return ber_tlv(0x02, raw)


def ber_str(text):
    return ber_tlv(0x04, text.encode("latin-1"))


def ber_null():
    return bytes([0x05, 0x00])


def ber_seq(*items, tag=0x30):
    body = b"".join(items)
    return ber_tlv(tag, body)


def ber_oid(numbers):
    out = [numbers[0] * 40 + numbers[1]]
    for n in numbers[2:]:
        if n < 0x80:
            out.append(n)
        else:
            chunk = []
            chunk.append(n & 0x7F)
            n >>= 7
            while n:
                chunk.insert(0, 0x80 | (n & 0x7F))
                n >>= 7
            out.extend(chunk)
    return ber_tlv(0x06, out)


def build_get_request(community, oid, request_id):
    varbind = ber_seq(ber_oid(oid), ber_null())
    pdu = ber_seq(
        ber_int(request_id),  # request-id
        ber_int(0),           # error-status
        ber_int(0),           # error-index
        ber_seq(varbind),
        tag=0xA0,             # GetRequest PDU
    )
    return ber_seq(ber_int(0), ber_str(community), pdu)  # version 0 = SNMPv1


# ---------------------------------------------------------------------------
# Парсинг docs/CVE_PRIORITY.md
# ---------------------------------------------------------------------------
def parse_cve_ips(path, cve_id):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    start = None
    for i, line in enumerate(lines):
        if cve_id in line and line.lstrip().startswith("#"):
            start = i
            break
    if start is None:
        raise ValueError(f"Раздел {cve_id} не найден в {path}")

    ips = []
    for line in lines[start + 1:]:
        if line.lstrip().startswith("#"):
            break
        m = re.match(r"^\|?\s*(\d{1,3}(?:\.\d{1,3}){3})\s*\|", line)
        if m:
            ips.append(m.group(1))
    return ips


# ---------------------------------------------------------------------------
# SNMP probing
# ---------------------------------------------------------------------------
def probe_community(ip, community, timeout, request_id):
    """True, если получен любой SNMP-ответ для данной community."""
    pkt = build_get_request(community, SYS_DESCR_OID, request_id)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(pkt, (ip, SNMP_PORT))
        data, _ = sock.recvfrom(4096)
        return bool(data) and data[0] == 0x30
    except socket.timeout:
        return False
    except OSError:
        return False
    finally:
        sock.close()


def scan_ips(ips, communities, timeout):
    open_results = []
    for ip in ips:
        hits = []
        for community in communities:
            if probe_community(ip, community, timeout, 0x12345678 ^ hits.__len__()):
                hits.append(community)
        if hits:
            open_results.append((ip, hits))
            print(f"  ⚠️  {ip:<16} SNMP ОТКРОТ — community: {', '.join(hits)}")
        else:
            print(f"  ✔  {ip:<16} SNMP закрыт / community не совпад")
    return open_results


def main():
    parser = argparse.ArgumentParser(
        description=f"Проверка SNMP для IP из раздела {CVE_ID} (MikroTik)")
    parser.add_argument("--file", default=DEFAULT_FILE,
                        help="Путь к CVE_PRIORITY.md (по умолчанию docs/CVE_PRIORITY.md)")
    parser.add_argument("--timeout", type=float, default=3.0,
                        help="Таймаут UDP-ответа в секундах (по умолчанию 3.0)")
    parser.add_argument("--communities", default="public,private",
                        help="Список community через запятую (по умолчанию public,private)")
    args = parser.parse_args()

    communities = [c.strip() for c in args.communities.split(",") if c.strip()]
    if not communities:
        print("Пустой список community", file=sys.stderr)
        return 2

    try:
        ips = parse_cve_ips(args.file, CVE_ID)
    except (OSError, ValueError) as exc:
        print(f"Ошибка чтения {args.file}: {exc}", file=sys.stderr)
        return 2
    if not ips:
        print(f"В разделе {CVE_ID} нет IP-адресов", file=sys.stderr)
        return 2

    print(f"{CVE_ID} — проверка SNMP (UDP 161), community: {', '.join(communities)}")
    print(f"IP из файла: {len(ips)}\n")

    open_results = scan_ips(ips, communities, args.timeout)

    print(f"\nИтог: {len(open_results)}/{len(ips)} IP с открытым SNMP")
    if open_results:
        print("Открытые:")
        for ip, hits in open_results:
            print(f"  {ip} — {', '.join(hits)}")
    return 1 if open_results else 0


if __name__ == "__main__":
    sys.exit(main())
