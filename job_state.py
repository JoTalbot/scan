#!/usr/bin/env python3
"""Durable, resumable and shard-idempotent scan job state.

State contains operational metadata only. Targets, credentials and secrets must
never be persisted here.
"""

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STATE_FILE = os.path.join(BASE_DIR, "job_state.json")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_job_id(job_id):
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("job_id must be a non-empty string")
    return job_id.strip()


def _validate_step(step):
    if not isinstance(step, str) or not step.strip():
        raise ValueError("step must be a non-empty string")
    return step.strip()


def _lock_path(path):
    return os.path.abspath(path) + ".lock"


@contextmanager
def _state_lock(path):
    """Serialize read-modify-write operations between local workers."""
    lock_path = _lock_path(path)
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as lock:
        try:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        except ImportError:  # pragma: no cover - Windows fallback
            pass
        try:
            yield
        finally:
            try:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            except ImportError:  # pragma: no cover
                pass


def load_state(path=DEFAULT_STATE_FILE):
    if not os.path.exists(path):
        return {"schema_version": 1, "jobs": {}}
    with open(path, "r", encoding="utf-8") as fh:
        state = json.load(fh)
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise ValueError("unsupported job state schema")
    state.setdefault("jobs", {})
    if not isinstance(state["jobs"], dict):
        raise ValueError("jobs must be an object")
    return state


def save_state(state, path=DEFAULT_STATE_FILE):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".job_state.", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def start_job(job_id, *, authorization_ref, scope_ref, state_path=DEFAULT_STATE_FILE):
    job_id = _validate_job_id(job_id)
    if not authorization_ref:
        raise PermissionError("authorization_ref is required")
    if not scope_ref:
        raise ValueError("scope_ref is required")
    with _state_lock(state_path):
        state = load_state(state_path)
        existing = state["jobs"].get(job_id)
        if existing and existing.get("status") == "completed":
            return existing
        record = existing or {
            "job_id": job_id,
            "status": "pending",
            "completed_steps": [],
            "completed_shards": [],
            "created_at": _now(),
        }
        record.setdefault("completed_shards", [])
        record.update({
            "status": "running",
            "scope_ref": str(scope_ref),
            "authorization_ref": str(authorization_ref),
            "updated_at": _now(),
        })
        state["jobs"][job_id] = record
        save_state(state, state_path)
        return record


def mark_step(job_id, step, *, state_path=DEFAULT_STATE_FILE):
    job_id = _validate_job_id(job_id)
    step = _validate_step(step)
    with _state_lock(state_path):
        state = load_state(state_path)
        if job_id not in state["jobs"]:
            raise KeyError(job_id)
        steps = state["jobs"][job_id].setdefault("completed_steps", [])
        if step not in steps:
            steps.append(step)
        state["jobs"][job_id]["updated_at"] = _now()
        save_state(state, state_path)
        return state["jobs"][job_id]


def step_completed(job_id, step, *, state_path=DEFAULT_STATE_FILE):
    return _validate_step(step) in load_state(state_path)["jobs"].get(
        _validate_job_id(job_id), {}
    ).get("completed_steps", [])


def complete_job(job_id, *, state_path=DEFAULT_STATE_FILE):
    job_id = _validate_job_id(job_id)
    with _state_lock(state_path):
        state = load_state(state_path)
        if job_id not in state["jobs"]:
            raise KeyError(job_id)
        state["jobs"][job_id].update({"status": "completed", "updated_at": _now()})
        save_state(state, state_path)
        return state["jobs"][job_id]


def shard_key(shard_id):
    if not isinstance(shard_id, str) or not shard_id.strip():
        raise ValueError("shard_id must be a non-empty string")
    return f"shard:{shard_id.strip()}"


def shard_completed(job_id, shard_id, *, state_path=DEFAULT_STATE_FILE):
    key = shard_key(shard_id)
    state = load_state(state_path)
    record = state["jobs"].get(_validate_job_id(job_id), {})
    return key in record.get("completed_shards", []) or key in record.get("completed_steps", [])


def mark_shard_completed(job_id, shard_id, *, state_path=DEFAULT_STATE_FILE):
    """Persist one shard completion marker under an inter-process lock."""
    job_id = _validate_job_id(job_id)
    key = shard_key(shard_id)
    with _state_lock(state_path):
        state = load_state(state_path)
        if job_id not in state["jobs"]:
            raise KeyError(job_id)
        shards = state["jobs"][job_id].setdefault("completed_shards", [])
        if key not in shards:
            shards.append(key)
        state["jobs"][job_id]["updated_at"] = _now()
        save_state(state, state_path)
        return state["jobs"][job_id]
