#!/usr/bin/env python3
"""Fail-closed resumable dispatcher for authorized scan shards."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from authorization import require_authorization
import job_state
import observability

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_BATCH = 10_000
DEFAULT_CONCURRENCY = 100
DEFAULT_MAX_CONCURRENCY = 500
DEFAULT_TIMEOUT = 2.0


def _positive_int(value, name):
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _bounded_concurrency(value, maximum):
    value = _positive_int(value, "concurrency")
    maximum = _positive_int(maximum, "max_concurrency")
    if value > maximum:
        raise ValueError(f"concurrency {value} exceeds max_concurrency {maximum}")
    return value


def _validate_ports(ports):
    if not ports:
        raise ValueError("ports must be a comma-separated list of TCP port numbers")
    parts = [part.strip() for part in ports.split(",")]
    if not parts or any(not part.isdigit() or not 1 <= int(part) <= 65535 for part in parts):
        raise ValueError("ports must be a comma-separated list of TCP port numbers")
    return ",".join(dict.fromkeys(parts))


def build_scan_command(batch, shard, total, ports, concurrency, timeout):
    return [sys.executable, str(BASE_DIR / "port_scanner.py"), "run",
            "--batch", str(batch), "--shard", str(shard), "--shard-total", str(total),
            "--concurrency", str(concurrency), "--timeout", str(timeout), "--ports", ports]


def _record_shard_and_maybe_complete(job_id, shard, total, state_kwargs):
    record = job_state.mark_shard_completed(job_id, str(shard), **state_kwargs)
    completed = set(record.get("completed_shards", []))
    observability.emit("shard.completed", job_id=job_id, shard=shard,
                       shard_total=total, completed_shards=len(completed))
    if len(completed) >= total:
        record = job_state.complete_job(job_id, **state_kwargs)
    return record


def run_shard(job_id, shard, total, *, batch=DEFAULT_BATCH, ports="80,8080,8443",
              concurrency=DEFAULT_CONCURRENCY, max_concurrency=DEFAULT_MAX_CONCURRENCY,
              timeout=DEFAULT_TIMEOUT, state_path=None):
    """Execute one authorized shard and persist completion only on success."""
    authorization = require_authorization()
    scope_ref = os.environ.get("SCAN_SCOPE_REF", "").strip()
    if not scope_ref:
        raise ValueError("SCAN_SCOPE_REF is required")
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("job_id is required")
    job_id = job_id.strip()
    total = _positive_int(total, "shard_total")
    if not isinstance(shard, int) or shard < 0:
        raise ValueError("shard must be a non-negative integer")
    if shard >= total:
        raise ValueError("shard must be less than shard_total")
    batch = _positive_int(batch, "batch")
    concurrency = _bounded_concurrency(concurrency, max_concurrency)
    timeout = float(timeout)
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    ports = _validate_ports(ports)

    kwargs = {"authorization_ref": authorization, "scope_ref": scope_ref}
    if state_path:
        kwargs["state_path"] = state_path
    job_state.start_job(job_id, **kwargs)
    state_kwargs = {"state_path": state_path} if state_path else {}
    state_file = state_path or job_state.DEFAULT_STATE_FILE
    record = job_state.load_state(state_file)["jobs"].get(job_id, {})
    if record.get("shard_total") not in (None, total):
        raise ValueError("shard_total does not match the existing job")
    if record.get("shard_total") is None:
        state = job_state.load_state(state_file)
        state["jobs"][job_id]["shard_total"] = total
        job_state.save_state(state, state_file)

    if job_state.shard_completed(job_id, str(shard), **state_kwargs):
        observability.emit("shard.skipped", job_id=job_id, shard=shard, reason="already_completed")
        return 0
    if job_state.load_state(state_file)["jobs"].get(job_id, {}).get("status") == "completed":
        observability.emit("shard.skipped", job_id=job_id, shard=shard, reason="job_completed")
        return 0

    observability.emit("shard.started", job_id=job_id, shard=shard, shard_total=total,
                       batch=batch, concurrency=concurrency, timeout=timeout)
    argv = build_scan_command(batch, shard, total, ports, concurrency, timeout)
    proc = subprocess.run(argv, cwd=BASE_DIR)
    if proc.returncode != 0:
        observability.emit("shard.failed", job_id=job_id, shard=shard,
                           shard_total=total, return_code=proc.returncode)
        return proc.returncode

    _record_shard_and_maybe_complete(job_id, shard, total, state_kwargs)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Resumable authorized scan shard executor")
    parser.add_argument("--job-id", default=os.environ.get("SCAN_JOB_ID", ""))
    parser.add_argument("--authorization-ref", default=os.environ.get("SCAN_AUTHORIZATION_REF", ""))
    parser.add_argument("--scope-ref", default=os.environ.get("SCAN_SCOPE_REF", ""))
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--shard-total", type=int, required=True)
    parser.add_argument("--batch", type=int, default=int(os.environ.get("SCAN_BATCH", DEFAULT_BATCH)))
    parser.add_argument("--ports", default=os.environ.get("SCAN_PORTS", "80,8080,8443"))
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("SCAN_CONCURRENCY", DEFAULT_CONCURRENCY)))
    parser.add_argument("--max-concurrency", type=int, default=int(os.environ.get("SCAN_MAX_CONCURRENCY", DEFAULT_MAX_CONCURRENCY)))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("SCAN_TIMEOUT", DEFAULT_TIMEOUT)))
    parser.add_argument("--state-path", default=os.environ.get("SCAN_JOB_STATE_PATH", ""))
    args = parser.parse_args(argv)
    if args.authorization_ref:
        os.environ["SCAN_AUTHORIZATION_REF"] = args.authorization_ref
    if args.scope_ref:
        os.environ["SCAN_SCOPE_REF"] = args.scope_ref
    if not args.job_id:
        parser.error("--job-id or SCAN_JOB_ID is required")
    return run_shard(args.job_id, args.shard, args.shard_total,
                     batch=args.batch, ports=args.ports, concurrency=args.concurrency,
                     max_concurrency=args.max_concurrency, timeout=args.timeout,
                     state_path=args.state_path or None)


if __name__ == "__main__":
    raise SystemExit(main())
