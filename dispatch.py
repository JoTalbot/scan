#!/usr/bin/env python3
"""Fail-closed dispatcher for RouterScan jobs.

Scan shards are always launched through ``resumable_dispatch.py`` so durable
job/shard state, authorization and bounded concurrency apply to every launch.
Non-scan legacy jobs remain available as single local subprocesses; active
scan/audit entrypoints enforce their own authorization boundaries.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from authorization import require_authorization

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_BATCH = 10_000
DEFAULT_CONCURRENCY = 100
DEFAULT_MAX_CONCURRENCY = 500
DEFAULT_TIMEOUT = 2.0


def _positive_int(value, name):
    value = int(value)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _workers(force_ssh=None):
    workers = []
    machines = force_ssh or os.environ.get("MACHINES", "")
    for machine in (m.strip() for m in machines.split(",")):
        if machine:
            workers.append(("ssh", machine))
    if shutil.which("gh"):
        try:
            result = subprocess.run(["gh", "auth", "status"], capture_output=True,
                                    text=True, timeout=15)
            if result.returncode == 0:
                workers.append(("codespaces", None))
        except (OSError, subprocess.SubprocessError):
            pass
    workers.append(("local", None))
    return workers


def _scan_argv(job_id, shard, total, batch, ports, concurrency, max_concurrency, timeout):
    return [
        sys.executable, str(BASE_DIR / "resumable_dispatch.py"),
        "--job-id", job_id,
        "--scope-ref", os.environ["SCAN_SCOPE_REF"],
        "--shard", str(shard), "--shard-total", str(total),
        "--batch", str(batch), "--ports", ports,
        "--concurrency", str(concurrency),
        "--max-concurrency", str(max_concurrency),
        "--timeout", str(timeout),
    ]


def _validate_scan(batch, shards, concurrency, max_concurrency, timeout):
    _positive_int(batch, "batch")
    _positive_int(shards, "shards")
    _positive_int(concurrency, "concurrency")
    _positive_int(max_concurrency, "max_concurrency")
    if concurrency > max_concurrency:
        raise ValueError("concurrency exceeds max_concurrency")
    if float(timeout) <= 0:
        raise ValueError("timeout must be positive")


def _run_local(argv, logfile=None):
    if logfile:
        logfile.parent.mkdir(parents=True, exist_ok=True)
        with logfile.open("w", encoding="utf-8") as log:
            return subprocess.run(argv, cwd=BASE_DIR, stdout=log, stderr=subprocess.STDOUT).returncode
    return subprocess.run(argv, cwd=BASE_DIR).returncode


def _run_ssh(machine, argv, logfile=None):
    """Run the remote resumable executor synchronously.

    SSH returning successfully means the executor itself returned successfully,
    which is required before the worker may consider the shard complete.
    """
    remote_root = "/root/scan"
    remote = "cd " + remote_root + " && " + " ".join(subprocess.list2cmdline([x]) for x in argv)
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", f"root@{machine}", remote]
    return _run_local(cmd, logfile)


def dispatch_scan(shards, batch, ports, parallel, force_ssh=None, job_id=None):
    """Dispatch all scan shards through the durable resumable executor."""
    authorization = require_authorization()
    scope_ref = os.environ.get("SCAN_SCOPE_REF", "").strip()
    if not scope_ref:
        raise PermissionError("SCAN_SCOPE_REF is required")
    if job_id is None:
        job_id = os.environ.get("SCAN_JOB_ID", "dispatch-scan")
    if not job_id.strip():
        raise ValueError("SCAN_JOB_ID is required")

    concurrency = int(os.environ.get("SCAN_CONCURRENCY", DEFAULT_CONCURRENCY))
    max_concurrency = int(os.environ.get("SCAN_MAX_CONCURRENCY", DEFAULT_MAX_CONCURRENCY))
    timeout = float(os.environ.get("SCAN_TIMEOUT", DEFAULT_TIMEOUT))
    _validate_scan(batch, shards, concurrency, max_concurrency, timeout)

    os.environ["SCAN_AUTHORIZATION_REF"] = authorization
    workers = _workers(force_ssh)
    assignments = [(workers[i % len(workers)], i) for i in range(shards)]
    procs = []
    log_dir = BASE_DIR / "logs" / "dispatch"

    for (worker_type, machine), shard in assignments:
        argv = _scan_argv(job_id, shard, shards, batch, ports,
                          concurrency, max_concurrency, timeout)
        logfile = log_dir / f"scan_shard{shard}.log"
        if worker_type == "ssh":
            if parallel:
                # A background local SSH process is safe because the remote
                # command itself is synchronous and runs the resumable executor.
                p = subprocess.Popen(
                    ["ssh", "-o", "StrictHostKeyChecking=no", f"root@{machine}",
                     "cd /root/scan && " + " ".join(subprocess.list2cmdline([x]) for x in argv)],
                    stdout=logfile.open("w", encoding="utf-8"), stderr=subprocess.STDOUT)
                procs.append((f"ssh:{machine}:shard{shard}", p))
            else:
                rc = _run_ssh(machine, argv, logfile)
                if rc != 0:
                    return rc
        else:
            if parallel:
                logfile.parent.mkdir(parents=True, exist_ok=True)
                log = logfile.open("w", encoding="utf-8")
                p = subprocess.Popen(argv, cwd=BASE_DIR, stdout=log, stderr=subprocess.STDOUT,
                                     env=os.environ.copy())
                p._dispatch_log = log  # type: ignore[attr-defined]
                procs.append((f"{worker_type}:shard{shard}", p))
            else:
                rc = _run_local(argv, logfile)
                if rc != 0:
                    return rc

    failed = 0
    for name, proc in procs:
        rc = proc.wait()
        log = getattr(proc, "_dispatch_log", None)
        if log:
            log.close()
        if rc != 0:
            print(f"❌ {name} failed (rc={rc})", file=sys.stderr)
            failed = rc or 1
    return failed


def dispatch(task, shards, batch, ports, parallel, force_ssh, task_text=""):
    if task == "scan":
        return dispatch_scan(shards, batch, ports, parallel, force_ssh)
    if task == "dev":
        if not task_text:
            raise ValueError("--task-text is required for dev")
        return _run_local([sys.executable, str(BASE_DIR / "openhands_agent.py"),
                           "--task", task_text])

    # Non-scan jobs intentionally remain single-process compatibility commands.
    # Their active network entrypoints retain their own fail-closed gates.
    commands = {
        "audit_raw": [sys.executable, str(BASE_DIR / "router_auth_check.py"), "--fast", "--concurrency", "30", "--timeout", "4"],
        "audit_browser": [sys.executable, str(BASE_DIR / "router_auth_browser.py"), "--only-no-channel", "--pairs", "8", "--concurrency", "4", "--timeout", "7", "--wait", "2.5"],
        "internetdb": [sys.executable, str(BASE_DIR / "internetdb_enrich.py"), "--delay", "0.2"],
        "probe": [sys.executable, str(BASE_DIR / "port_probe.py"), "--concurrency", "50", "--timeout", "2"],
    }
    if task not in commands:
        raise ValueError(f"unsupported dispatch task: {task}")
    require_authorization()
    return _run_local(commands[task])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fail-closed RouterScan dispatcher")
    parser.add_argument("task", nargs="?", choices=["scan", "dev", "audit_raw", "audit_browser", "internetdb", "probe"])
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--batch", type=int, default=int(os.environ.get("SCAN_BATCH", DEFAULT_BATCH)))
    parser.add_argument("--ports", default=os.environ.get("SCAN_PORTS", "80,8080,8443"))
    parser.add_argument("--parallel", action="store_true")
    parser.add_argument("--force-ssh")
    parser.add_argument("--workers", action="store_true")
    parser.add_argument("--task-text")
    parser.add_argument("--job-id", default=os.environ.get("SCAN_JOB_ID", "dispatch-scan"))
    args = parser.parse_args(argv)

    if args.workers or not args.task:
        for kind, machine in _workers(args.force_ssh):
            print(f"{kind}: {machine or 'local'}")
        return 0

    if args.task == "scan":
        os.environ["SCAN_JOB_ID"] = args.job_id
    return dispatch(args.task, args.shards, args.batch, args.ports,
                    args.parallel, args.force_ssh, args.task_text)


if __name__ == "__main__":
    raise SystemExit(main())
