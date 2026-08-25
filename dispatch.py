#!/usr/bin/env python3
"""
RouterScan Dispatcher — раздача задач по исполнителям (машинам)
================================================================
Генерирует N шардов задачи и раздаёт их доступным исполнителям:

  * local      — N процессов на этом сервере (всегда доступен)
  * ssh        — машины из MACHINES="ip1,ip2,..." (Oracle ARM, VPS и т.д.)
  * codespaces — GitHub Codespaces через gh CLI (если установлен+авторизован)
  * e2b        — E2B песочницы (если есть E2B_API_KEY)

Порядок приоритета: ssh → codespaces → e2b → local (последние добивают local'ом).

Задачи:
  * scan        — port_scanner.py run --batch N --shard i/total
  * audit_raw   — router_auth_check.py --fast
  * audit_browser — router_auth_browser.py --only-no-channel
  * internetdb  — internetdb_enrich.py
  * probe       — port_probe.py

Usage:
    python3 dispatch.py scan --batch 100000 --shards 4
    python3 dispatch.py audit_raw --shards 2
    python3 dispatch.py scan --batch 100000 --shards 6 --force-ssh "10.0.0.2,10.0.0.3"
    MACHINES="10.0.0.2,10.0.0.3" python3 dispatch.py scan --batch 100000 --shards 4

Флаг --parallel: исполнители работают одновременно (по умолчанию последовательно).
"""

import os
import sys
import time
import json
import shutil
import argparse
import subprocess
import datetime

REPO = "https://github.com/JoTalbot/scan.git"
TASKS = {
    "scan": {
        "cmd": "python3 port_scanner.py run --batch {batch} --shard {shard} --shard-total {total} "
               "--concurrency 1000 --timeout 1.0 --ports {ports}",
        "local_ok": True, "ssh_ok": True, "codespaces_ok": True, "e2b_ok": True,
    },
    "audit_raw": {
        "cmd": "python3 router_auth_check.py --fast --concurrency 30 --timeout 4",
        "local_ok": True, "ssh_ok": True, "codespaces_ok": True, "e2b_ok": True,
    },
    "audit_browser": {
        "cmd": ".venv/bin/python -u router_auth_browser.py --only-no-channel --pairs 8 "
               "--concurrency 4 --timeout 7 --wait 2.5",
        "local_ok": True, "ssh_ok": True, "codespaces_ok": True, "e2b_ok": True,
    },
    "internetdb": {
        "cmd": "python3 internetdb_enrich.py --delay 0.2",
        "local_ok": True, "ssh_ok": True, "codespaces_ok": True, "e2b_ok": True,
    },
    "probe": {
        "cmd": "python3 port_probe.py --concurrency 50 --timeout 2",
        "local_ok": True, "ssh_ok": True, "codespaces_ok": True, "e2b_ok": True,
    },
}


def get_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Исполнители
# ---------------------------------------------------------------------------
def available_workers(force_ssh=None):
    """Возвращает список доступных исполнителей с их ёмкостью (сколько шардов могут взять)."""
    workers = []

    # 1. SSH-машины
    machines = force_ssh or os.environ.get("MACHINES", "")
    if machines:
        ssh_list = [m.strip() for m in machines.split(",") if m.strip()]
        if ssh_list:
            workers.append({"type": "ssh", "machines": ssh_list})

    # 2. Codespaces (gh CLI)
    gh = shutil.which("gh")
    gh_ok = False
    if gh:
        r = subprocess.run([gh, "auth", "status"], capture_output=True, text=True, timeout=15)
        gh_ok = r.returncode == 0
    if gh_ok:
        workers.append({"type": "codespaces", "cli": gh})

    # 3. E2B
    if os.environ.get("E2B_API_KEY"):
        workers.append({"type": "e2b"})

    # 4. local (всегда)
    workers.append({"type": "local"})

    return workers


def run_local(cmd, logfile, env_extra=None):
    """Запуск команды локально в фоне."""
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    log = open(logfile, "w")
    p = subprocess.Popen(f"ulimit -n 65535 2>/dev/null; {cmd}", shell=True,
                         stdout=log, stderr=subprocess.STDOUT, env=env)
    return p


def run_ssh(machine, cmd, logfile):
    """Запуск команды на SSH-машине в фоне."""
    log = open(logfile, "w")
    remote = f"cd /root/scan && git pull --rebase origin main 2>/dev/null; ulimit -n 65535 2>/dev/null; {cmd} > /root/scan/logs/dispatch.log 2>&1 &"
    p = subprocess.Popen(["ssh", "-o", "StrictHostKeyChecking=no", f"root@{machine}", remote],
                         stdout=log, stderr=subprocess.STDOUT)
    return p


def run_codespaces(cli, cmd, logfile, name):
    """Запуск в Codespace через gh CLI."""
    log = open(logfile, "w")
    # создание кодаспейса и выполнение команды
    r = subprocess.run([cli, "codespace", "create", "--repo", REPO, "--display-name", name],
                       capture_output=True, text=True, timeout=300)
    cs_name = None
    for line in (r.stdout or "").splitlines():
        if line.strip():
            cs_name = line.strip().split()[-1]
    if not cs_name:
        log.write(f"codespace create failed: {r.stdout} {r.stderr}")
        log.close()
        return None
    time.sleep(10)  # даём загрузиться
    p = subprocess.Popen([cli, "codespace", "ssh", "-c", "-c", cmd, "-c", "-c", cs_name],
                         stdout=log, stderr=subprocess.STDOUT)
    p.cs_name = cs_name  # type: ignore
    return p


def run_e2b(script_cmd, logfile, shard):
    """Запуск в E2B песочнице через e2b_audit.py."""
    log = open(logfile, "w")
    p = subprocess.Popen([sys.executable, "e2b_audit.py", "--script", script_cmd.split()[0],
                          "--args", " ".join(script_cmd.split()[1:])],
                         stdout=log, stderr=subprocess.STDOUT)
    return p


# ---------------------------------------------------------------------------
# Раздача
# ---------------------------------------------------------------------------
def dispatch(task, shards, batch, ports, parallel, force_ssh):
    cfg = TASKS[task]
    workers = available_workers(force_ssh)
    print(f"[{get_now()}] Задача: {task} | шардов: {shards} | исполнители: "
          f"{[w['type'] for w in workers]}")

    os.makedirs("logs/dispatch", exist_ok=True)
    procs = []  # (name, proc, worker_type)

    # сканирование раздаётся по шардам; остальные задачи — целые на исполнителях
    if task == "scan":
        # распределяем шарды по исполнителям
        assignments = []  # (worker_type, machine_or_None, shard)
        wi = 0
        for shard in range(shards):
            w = workers[wi % len(workers)]
            assignments.append((w["type"], w.get("machines", [None])[wi // len(workers)] if w["type"] == "ssh" and w.get("machines") else None, shard))
            wi += 1

        for i, (wtype, machine, shard) in enumerate(assignments):
            cmd = cfg["cmd"].format(batch=batch, shard=shard, total=shards, ports=ports)
            name = f"shard{shard}"
            logfile = f"logs/dispatch/{task}_{name}.log"
            if wtype == "local":
                p = run_local(cmd, logfile)
                procs.append((f"local:{name}", p, "local"))
                print(f"  ➡️  {name}: local")
            elif wtype == "ssh":
                p = run_ssh(machine, cmd, logfile)
                procs.append((f"ssh:{machine}:{name}", p, "ssh"))
                print(f"  ➡️  {name}: ssh {machine}")
            elif wtype == "codespaces":
                p = run_codespaces(workers[i]["cli"], cmd, logfile, f"rs-{name}")
                if p:
                    procs.append((f"codespaces:{name}", p, "codespaces"))
                    print(f"  ➡️  {name}: codespaces")
            elif wtype == "e2b":
                p = run_e2b(cmd, logfile, shard)
                procs.append((f"e2b:{name}", p, "e2b"))
                print(f"  ➡️  {name}: e2b")
    else:
        # не-скан задачи: по одной на исполнителя (по кругу)
        for i, w in enumerate(workers):
            cmd = cfg["cmd"]
            name = f"job{i}"
            logfile = f"logs/dispatch/{task}_{name}.log"
            if w["type"] == "local":
                p = run_local(cmd, logfile)
                procs.append((f"local:{name}", p, "local"))
            elif w["type"] == "ssh":
                p = run_ssh(w["machines"][0], cmd, logfile)
                procs.append((f"ssh:{w['machines'][0]}:{name}", p, "ssh"))
            elif w["type"] == "codespaces":
                p = run_codespaces(w["cli"], cmd, logfile, f"rs-{name}")
                if p:
                    procs.append((f"codespaces:{name}", p, "codespaces"))
            elif w["type"] == "e2b":
                p = run_e2b(cmd, logfile, i)
                procs.append((f"e2b:{name}", p, "e2b"))
            print(f"  ➡️  {name}: {w['type']}")

    # мониторинг
    print(f"\n[{get_now()}] Запущено: {len(procs)} исполнителей")
    if parallel:
        # ждём все
        while procs:
            done = []
            for name, p, wtype in procs:
                if p.poll() is not None:
                    rc = p.returncode
                    print(f"[{get_now()}] ✅ {name} завершён (rc={rc})")
                    done.append((name, p, wtype))
            for d in done:
                procs.remove(d)
            if procs:
                time.sleep(15)
    else:
        # последовательно: ждём по одному
        for name, p, wtype in procs:
            print(f"[{get_now()}] ожидание {name}...")
            p.wait()
            print(f"[{get_now()}] ✅ {name} завершён (rc={p.returncode})")

    # сборка: синхронизация после всех (лучше делать на шарде 0 / главной машине)
    print(f"\n[{get_now()}] Все исполнители завершены. Запускаю sync...")
    if task == "scan":
        subprocess.run([sys.executable, "sync_manager.py", "dispatch"], cwd="/root/scan")
    print(f"[{get_now()}] ✅ Готово")


def main():
    parser = argparse.ArgumentParser(description="RouterScan Dispatcher")
    parser.add_argument("task", nargs="?", choices=list(TASKS.keys()), help="Тип задачи")
    parser.add_argument("--shards", type=int, default=4, help="Число шардов (для scan)")
    parser.add_argument("--batch", type=int, default=100000, help="Batch для scan")
    parser.add_argument("--ports", default="80,8080,8443", help="Порты для scan")
    parser.add_argument("--parallel", action="store_true", help="Параллельно, а не последовательно")
    parser.add_argument("--force-ssh", help="Принудительно использовать эти SSH-машины (через запятую)")
    parser.add_argument("--workers", action="store_true", help="Показать доступных исполнителей")
    args = parser.parse_args()

    if args.workers or not args.task:
        ws = available_workers(args.force_ssh)
        print("Доступные исполнители:")
        for w in ws:
            if w["type"] == "ssh":
                print(f"  ssh: {w['machines']}")
            elif w["type"] == "codespaces":
                print("  codespaces (gh CLI авторизован)")
            elif w["type"] == "e2b":
                print("  e2b (ключ есть)")
            else:
                print("  local")
        print("\nЗадачи:", ", ".join(TASKS.keys()))
        print("Пример: python3 dispatch.py scan --batch 100000 --shards 4")
        return

    dispatch(args.task, args.shards, args.batch, args.ports, args.parallel, args.force_ssh)


if __name__ == "__main__":
    main()
