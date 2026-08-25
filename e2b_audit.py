#!/usr/bin/env python3
"""
E2B Sandbox Auditor (№4 плана)
===============================
Запускает скрипты RouterScan-проекта в изолированной E2B-песочнице
(Firecracker microVM) — тяжёлый аудит (Playwright и пр.) не нагружает
основной сервер. До 20 параллельных песочниц на Hobby-плане ($100 кредитов).

Требуется: pip install e2b; E2B_API_KEY (e2b.dev → API keys).

Usage:
    python3 e2b_audit.py --script router_auth_check.py --args "--fast --vendor MIKROTIK"
    python3 e2b_audit.py --script router_auth_browser.py --args "--only-no-channel --pairs 8"
    python3 e2b_audit.py --script port_probe.py --args "--targets 1.2.3.4"
    python3 e2b_audit.py --script cve_check.py          # без аргументов
    python3 e2b_audit.py --list                        # список скриптов

Файлы результатов (isp_cidr.db, data/, *.md) скачиваются в downloads/.
"""

import os
import sys
import time
import argparse

REPO = "https://github.com/JoTalbot/scan.git"
SCRIPTS = ["router_auth_check.py", "router_auth_browser.py", "port_probe.py",
           "cve_check.py", "bgp_looking_glass.py", "internetdb_enrich.py",
           "verify_findings.py", "extract_routers.py"]

SETUP_CMDS = [
    "git clone --depth 1 {repo} /scan && cd /scan",
    "apt-get update -qq && apt-get install -y -qq git-lfs 2>/dev/null || true",
    "git lfs install && git lfs pull 2>/dev/null || true",   # скачивание реальной БД из LFS
    "pip install --quiet paramiko playwright==1.62.0 pytest 2>/dev/null || true",
    "python -m playwright install chromium 2>/dev/null || true",
    "gunzip -kf isp_cidr.db.gz 2>/dev/null || true",
]


def main():
    parser = argparse.ArgumentParser(description="E2B sandbox auditor")
    parser.add_argument("--script", help="Скрипт из репо для запуска")
    parser.add_argument("--args", default="", help="Аргументы для скрипта")
    parser.add_argument("--list", action="store_true", help="Список доступных скриптов")
    parser.add_argument("--timeout", type=int, default=60 * 55, help="Таймаут сессии (сек)")
    parser.add_argument("--template", default="base", help="Шаблон песочницы E2B")
    parser.add_argument("--keep", action="store_true", help="Не удалять песочницу после")
    args = parser.parse_args()

    if args.list:
        print("Доступные скрипты:")
        for s in SCRIPTS:
            print(f"  {s}")
        return

    if not args.script:
        parser.print_help()
        return

    if args.script not in SCRIPTS:
        print(f"Скрипт {args.script} не в списке: {SCRIPTS}")
        return

    api_key = os.environ.get("E2B_API_KEY")
    if not api_key:
        print("❌ Нет E2B_API_KEY. Получите на https://e2b.dev (Sign up → API keys),")
        print("   затем: export E2B_API_KEY=e2b_...")
        sys.exit(1)

    try:
        from e2b import Sandbox
    except ImportError:
        print("❌ Установите SDK: pip install e2b")
        sys.exit(1)

    print(f"🚀 Создаю E2B-песочницу...")
    sandbox = Sandbox.create()
    try:
        # 1. клонирование и подготовка
        for cmd in SETUP_CMDS:
            cmd = cmd.format(repo=REPO)
            print(f"  ⚙️ {cmd[:80]}...")
            proc = sandbox.commands.run(cmd, timeout=300)
            if proc.exit_code not in (0, None):
                print(f"  ⚠️ exit={proc.exit_code}: {proc.stderr[-300:] if proc.stderr else ''}")

        # 2. запуск целевого скрипта
        full = f"cd /scan && python3 {args.script} {args.args}"
        print(f"🚀 Запуск: {full}")
        proc = sandbox.commands.run(full, timeout=args.timeout - 60)
        out = (proc.stdout or "")[-4000:]
        err = (proc.stderr or "")[-2000:]
        print("=" * 60)
        print("=== STDOUT ===")
        print(out)
        if err:
            print("=== STDERR ===")
            print(err)
        print("=" * 60)
        print(f"exit_code: {proc.exit_code}")

        # 3. скачиваем результаты
        os.makedirs("downloads", exist_ok=True)
        for f in ["isp_cidr.db", "data/routers", "data/creds", "REPORT.md",
                  "CVE_REPORT.md", "internetdb_report.md", "router_credentials.csv"]:
            try:
                sandbox.files.download(f"/scan/{f}", f"downloads/{os.path.basename(f)}")
                print(f"  📥 Скачано: {f}")
            except Exception:
                pass  # файла может не быть

        if args.keep:
            print(f"ℹ️ Песочница сохранена: {sandbox.sandbox_id} (удалите вручную)")
        else:
            print("🗑 Удаляю песочницу...")
            sandbox.kill()
            print("✅ Готово")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        try:
            sandbox.kill()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
