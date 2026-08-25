#!/usr/bin/env python3
"""
Orchestrator — бесконечный цикл сканирования и аудита
======================================================
Фоновый процесс: сканирует батчами по 100k IP, после каждого скана
запускает аудит-цепочку (пароли raw, browser, CodeSandbox, InternetDB),
синхронизирует с GitHub и повторяет цикл бесконечно (пока не остановлен).

Управление:
  python3 orchestrator.py start     # запуск в фоне
  python3 orchestrator.py stop      # остановка после текущего цикла
  python3 orchestrator.py status    # текущее состояние

Веб-панель (web_server.py) управляет через state-файл:
  POST /api/control {action: start|stop}
  GET  /api/status

State: orchestrator_state.json
"""
import os
import sys
import json
import time
import signal
import logging
import datetime
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "orchestrator_state.json")
LOG_FILE = os.path.join(BASE_DIR, "logs", "orchestrator.log")
PID_FILE = os.path.join(BASE_DIR, "orchestrator.pid")

BATCH = int(os.environ.get("ORCH_BATCH", "100000"))
PORTS = os.environ.get("ORCH_PORTS", "80,8080,8443")
STEPS = {
    "scan": "python3 port_scanner.py run --batch {batch} --concurrency 1000 --timeout 1.0 --ports {ports}",
    "raw_audit": "python3 router_auth_check.py --fast --concurrency 30 --timeout 4",
    "browser_audit": ".venv/bin/python -u router_auth_browser.py --only-no-channel --pairs 8 --concurrency 4 --timeout 7 --wait 2.5",
    "csb_probe": "python3 dispatch.py csb_probe --batch 20",
    "e2b_probe": "python3 dispatch.py e2b_probe --batch 20",
    "internetdb": "python3 internetdb_enrich.py --delay 0.2",
    "sync": "python3 sync_manager.py orchestrator",
}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"state": "STOPPED", "current_step": "idle", "cycles": 0,
            "last_cycle": None, "last_scan_at": None, "last_scan_ips": 0,
            "last_routers_found": 0, "total_routers": 0, "errors": [], "started_at": None}


def save_state(**updates):
    st = get_state()
    st.update(updates)
    st["updated_at"] = now()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def setup_logger():
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
    logger = logging.getLogger("orchestrator")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(fh)
    return logger


def run_step(logger, name, cmd, timeout=3600, interruptible=False):
    """Запуск шага, логирование. Если interruptible — при STOPPING убивает процесс."""
    logger.info(f"STEP {name}: {cmd[:100]}")
    save_state(current_step=name)
    env = dict(os.environ)
    p = None
    try:
        p = subprocess.Popen(f"cd {BASE_DIR} && ulimit -n 65535 2>/dev/null; {cmd}",
                             shell=True, env=env, start_new_session=True,
                             stdout=open(os.path.join(BASE_DIR, "logs", f"orchestrator_{name}.log"), "w"),
                             stderr=subprocess.STDOUT)
        # ждём с проверкой остановки каждые 5 сек (если interruptible)
        while True:
            try:
                rc = p.wait(timeout=5)
                logger.info(f"STEP {name} done rc={rc}")
                return rc
            except subprocess.TimeoutExpired:
                if interruptible and get_state().get("state") == "STOPPING":
                    logger.info(f"STEP {name} прерван (STOPPING)")
                    _kill_proc(p)
                    return -2  # прерван
                continue
    except Exception as e:
        logger.error(f"STEP {name} error: {e}")
        if p:
            _kill_proc(p)
        return -1


def _kill_proc(p):
    """Мягко остановить процесс и его детей: SIGTERM, ждём 5с, затем SIGKILL.
    SIGKILL сразу опасен для SQLite (повреждение WAL) — поэтому сначала TERM."""
    import signal as _sig
    try:
        os.killpg(os.getpgid(p.pid), _sig.SIGTERM)
    except Exception:
        try:
            p.terminate()
        except Exception:
            pass
    # ждём graceful shutdown
    try:
        p.wait(timeout=5)
        return
    except Exception:
        pass
    # не завершился — жёсткий kill (последний резерв)
    try:
        os.killpg(os.getpgid(p.pid), _sig.SIGKILL)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def db_count(table="scan_routers"):
    try:
        import sqlite3
        conn = sqlite3.connect(os.path.join(BASE_DIR, "isp_cidr.db"))
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


def run_cycle(logger):
    """Один полный цикл: скан → аудит → sync. Возвращает сводку."""
    logger.info("=== CYCLE START ===")
    save_state(current_step="scan")

    # 1. скан батча (НЕ прерывается — дожидается конца 100k)
    rc = run_step(logger, "scan", STEPS["scan"].format(batch=BATCH, ports=PORTS),
                  timeout=3600, interruptible=False)

    routers_before = db_count()
    new_routers = db_count() - routers_before if routers_before >= 0 else 0
    # точнее: считаем по detected_at
    try:
        import sqlite3
        conn = sqlite3.connect(os.path.join(BASE_DIR, "isp_cidr.db"))
        since = (datetime.datetime.now(datetime.timezone.utc) -
                 datetime.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_routers = conn.execute(
            "SELECT COUNT(*) FROM scan_routers WHERE detected_at >= ?", (since,)).fetchone()[0]
        conn.close()
    except Exception:
        pass

    total = db_count()
    save_state(last_scan_at=now(), last_routers_found=new_routers, total_routers=total)

    # 2. аудит-цепочка (проверяем, есть ли что аудитить)
    import sqlite3
    conn = sqlite3.connect(os.path.join(BASE_DIR, "isp_cidr.db"))
    pending_raw = conn.execute("SELECT COUNT(*) FROM scan_routers WHERE auth_checked=0").fetchone()[0]
    pending_br = conn.execute(
        "SELECT COUNT(*) FROM scan_routers WHERE browser_checked=0 AND auth_result='no-verifiable-channel'").fetchone()[0]
    conn.close()

    def stopping():
        return get_state().get("state") == "STOPPING"

    # Остальные модули прерываются СРАЗУ при STOPPING (максимум 5 сек задержки)
    if pending_raw > 0:
        rc2 = run_step(logger, "raw_audit", STEPS["raw_audit"], timeout=900, interruptible=True)
        if rc2 == -2:
            logger.info("STOP — останавливаю остальные модули")
            return _finish_cycle(logger, rc, new_routers, total, pending_raw, pending_br)
    if pending_br > 0:
        rc2 = run_step(logger, "browser_audit", STEPS["browser_audit"], timeout=2400, interruptible=True)
        if rc2 == -2:
            logger.info("STOP — останавливаю остальные модули")
            return _finish_cycle(logger, rc, new_routers, total, pending_raw, pending_br)
    if pending_br > 0:
        rc2 = run_step(logger, "csb_probe", STEPS["csb_probe"], timeout=1200, interruptible=True)
        if rc2 == -2:
            return _finish_cycle(logger, rc, new_routers, total, pending_raw, pending_br)
        rc2 = run_step(logger, "e2b_probe", STEPS["e2b_probe"], timeout=1200, interruptible=True)
        if rc2 == -2:
            return _finish_cycle(logger, rc, new_routers, total, pending_raw, pending_br)
    if new_routers > 0:
        run_step(logger, "internetdb", STEPS["internetdb"], timeout=600, interruptible=True)

    # 3. sync (всегда выполняется, но тоже прерываемый — если стоп нажат)
    rc2 = run_step(logger, "sync", STEPS["sync"], timeout=900, interruptible=True)
    return _finish_cycle(logger, rc, new_routers, total, pending_raw, pending_br)


def _finish_cycle(logger, rc, new_routers, total, pending_raw, pending_br):
    """Финализация цикла: sync (всегда!) + сводка + счётчик."""
    # результаты всегда попадают в git, даже при остановке
    if get_state().get("state") == "STOPPING" or new_routers > 0:
        run_step(logger, "sync", STEPS["sync"], timeout=900)
    cycles = get_state().get("cycles", 0) + 1
    save_state(current_step="idle", cycles=cycles,
               last_cycle={"at": now(), "scan_rc": rc, "new_routers": new_routers,
                           "total_routers": total, "pending_raw": pending_raw,
                           "pending_browser": pending_br})
    logger.info(f"=== CYCLE DONE #{cycles}: new_routers={new_routers} total={total} ===")
    return cycles

    cycles = get_state().get("cycles", 0) + 1
    save_state(current_step="idle", cycles=cycles,
               last_cycle={"at": now(), "scan_rc": rc, "new_routers": new_routers,
                           "total_routers": total, "pending_raw": pending_raw,
                           "pending_browser": pending_br})
    logger.info(f"=== CYCLE DONE #{cycles}: new_routers={new_routers} total={total} ===")
    return cycles


def main_loop(logger):
    save_state(state="RUNNING", current_step="startup", started_at=now(), errors=[])
    logger.info("Orchestrator started")
    cycles = 0
    while True:
        st = get_state()
        if st.get("state") == "STOPPING":
            save_state(state="STOPPED", current_step="idle")
            logger.info("Stopped after cycle completion")
            break
        try:
            cycles = run_cycle(logger)
        except Exception as e:
            logger.error(f"Cycle error: {e}")
            errs = get_state().get("errors", [])
            errs.append(str(e)[:200])
            save_state(errors=errs[-10:])
        # пауза между циклами (проверка стопа)
        for _ in range(6):  # 6 x 10s = 60s
            if get_state().get("state") == "STOPPING":
                break
            time.sleep(10)


def start():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            print(f"Orchestrator уже запущен (pid={pid})")
            return
        except (ProcessLookupError, ValueError):
            pass
    logger = setup_logger()
    p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "_loop"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    with open(PID_FILE, "w") as f:
        f.write(str(p.pid))
    save_state(state="RUNNING", current_step="starting")
    print(f"✅ Orchestrator запущен (pid={p.pid})")


def stop():
    save_state(state="STOPPING", current_step="stopping")
    print("🛑 Остановка после завершения текущего цикла...")


def status():
    st = get_state()
    print(json.dumps(st, ensure_ascii=False, indent=2))


def _loop():
    logger = setup_logger()
    main_loop(logger)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "status":
        status()
    elif cmd == "_loop":
        _loop()
    else:
        print(__doc__)
