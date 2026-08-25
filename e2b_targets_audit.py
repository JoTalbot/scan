#!/usr/bin/env python3
"""
E2B Targets Audit — аудит списка IP без большой БД
====================================================
Основная БД (716 МБ) не помещается в E2B-песочницу (478 МБ RAM) вместе со
сканом. Решение: цели (IP-адреса) передаются списком через аргументы,
аудитор работает только с этим списком — памяти хватает.

Запуск:
  python3 e2b_targets_audit.py --targets "1.2.3.4,5.6.7.8" --mode http
  python3 e2b_targets_audit.py --targets-file targets.txt --mode http

Моды:
  http   — проверить HTTP-баннеры переданных IP (GET /, заголовки)
  reach  — только TCP-доступность портов 80/443/8080/8443

Результаты печатаются в stdout (и собираются диспетчером).
"""
import os
import sys
import json
import socket
import argparse
import datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RouterScan"


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_banner(ip, port=80, timeout=4):
    """Простейший HTTP-баннер (как в сканере, но без БД)."""
    try:
        s = socket.create_connection((ip, port), timeout=timeout)
        s.sendall(f"GET / HTTP/1.1\r\nHost: {ip}\r\nUser-Agent: {UA}\r\nConnection: close\r\n\r\n".encode())
        s.settimeout(timeout)
        data = b""
        while True:
            try:
                chunk = s.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            data += chunk
            if len(data) > 4096:
                break
        s.close()
        text = data.decode("utf-8", errors="ignore")
        lines = text.split("\r\n")
        status = lines[0][:40] if lines else ""
        srv = next((l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("server:")), "")
        return {"ip": ip, "port": port, "status": status, "server": srv[:80],
                "len": len(data)}
    except Exception as e:
        return {"ip": ip, "port": port, "error": str(e)[:60]}


def tcp_check(ip, port, timeout=3):
    try:
        s = socket.create_connection((ip, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", help="IP через запятую")
    parser.add_argument("--targets-file", help="Файл с IP (по одному на строку)")
    parser.add_argument("--mode", default="http", choices=["http", "reach"])
    parser.add_argument("--ports", default="80,8080,8443")
    parser.add_argument("--concurrency", type=int, default=20, help="Не используется (socket sync), для совместимости")
    args = parser.parse_args()

    ips = []
    if args.targets:
        ips = [x.strip() for x in args.targets.split(",") if x.strip()]
    elif args.targets_file and os.path.exists(args.targets_file):
        ips = [l.strip() for l in open(args.targets_file) if l.strip()]
    if not ips:
        print("Нет целей")
        sys.exit(1)

    print(f"🎯 Целей: {len(ips)} | mode={args.mode}", flush=True)
    results = []
    for i, ip in enumerate(ips):
        if args.mode == "http":
            res = http_banner(ip, 80)
        else:
            res = {"ip": ip, "open": [p for p in (80, 443, 8080, 8443) if tcp_check(ip, p)]}
        results.append(res)
        if (i + 1) % 10 == 0 or i + 1 == len(ips):
            print(f"  🔄 [{i+1}/{len(ips)}]", flush=True)
    print("\n=== РЕЗУЛЬТАТЫ ===")
    print(json.dumps(results, ensure_ascii=False))
    print(f"\n✅ Готово: {len(results)} целей")


if __name__ == "__main__":
    main()
