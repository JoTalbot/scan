#!/usr/bin/env python3
"""Bounded scheduling primitives for RouterScan 1.4 reliability.

This module is orchestration-only. It does not authorize or perform network
operations; active scan entrypoints remain fail-closed behind authorization.py.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Callable, Optional


def deterministic_task_id(job_id: str, shard: str) -> str:
    """Return a stable opaque task id without embedding target data."""
    raw = f"{job_id.strip()}\0{shard.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


@dataclass(order=True)
class _QueuedTask:
    priority: int
    sequence: int
    task_id: str = field(compare=False)
    fn: Callable[[], object] = field(compare=False)


class RetryBudget:
    """Bounded retry counter keyed by deterministic task id."""

    def __init__(self, max_attempts: int = 3):
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self.max_attempts = max_attempts
        self._attempts: dict[str, int] = {}
        self._lock = threading.Lock()

    def allow(self, task_id: str) -> bool:
        with self._lock:
            attempts = self._attempts.get(task_id, 0)
            if attempts >= self.max_attempts:
                return False
            self._attempts[task_id] = attempts + 1
            return True

    def attempts(self, task_id: str) -> int:
        with self._lock:
            return self._attempts.get(task_id, 0)


class CircuitBreaker:
    """Small failure circuit for external worker/dependency calls."""

    def __init__(self, threshold: int = 3, cooldown: float = 30.0):
        if threshold <= 0 or cooldown <= 0:
            raise ValueError("threshold and cooldown must be positive")
        self.threshold = threshold
        self.cooldown = float(cooldown)
        self.failures = 0
        self.opened_at: Optional[float] = None
        self._lock = threading.Lock()

    def allow(self, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            if self.opened_at is None:
                return True
            if now - self.opened_at >= self.cooldown:
                self.opened_at = None
                self.failures = 0
                return True
            return False

    def success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_at = None

    def failure(self, now: Optional[float] = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = now


@dataclass
class WorkerLease:
    task_id: str
    worker_id: str
    acquired_at: float
    expires_at: float

    def expired(self, now: Optional[float] = None) -> bool:
        return (time.monotonic() if now is None else now) >= self.expires_at


class LeaseRegistry:
    """Thread-safe leases with heartbeat and expiry-based reassignment."""

    def __init__(self, lease_seconds: float = 60.0):
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.lease_seconds = float(lease_seconds)
        self._leases: dict[str, WorkerLease] = {}
        self._lock = threading.Lock()

    def acquire(self, task_id: str, worker_id: str, now: Optional[float] = None) -> WorkerLease:
        now = time.monotonic() if now is None else now
        with self._lock:
            existing = self._leases.get(task_id)
            if existing and not existing.expired(now):
                raise RuntimeError("task lease is already active")
            lease = WorkerLease(task_id, worker_id, now, now + self.lease_seconds)
            self._leases[task_id] = lease
            return lease

    def heartbeat(self, task_id: str, worker_id: str, now: Optional[float] = None) -> WorkerLease:
        now = time.monotonic() if now is None else now
        with self._lock:
            lease = self._leases.get(task_id)
            if not lease or lease.worker_id != worker_id or lease.expired(now):
                raise RuntimeError("lease is missing or expired")
            lease.expires_at = now + self.lease_seconds
            return lease

    def release(self, task_id: str, worker_id: str) -> None:
        with self._lock:
            lease = self._leases.get(task_id)
            if lease and lease.worker_id == worker_id:
                self._leases.pop(task_id, None)

    def expired_tasks(self, now: Optional[float] = None) -> list[str]:
        now = time.monotonic() if now is None else now
        with self._lock:
            return [task_id for task_id, lease in self._leases.items() if lease.expired(now)]


class BoundedScheduler:
    """Priority queue with deduplication, bounded concurrency and clean stop."""

    def __init__(self, max_workers: int = 4, max_queue: int = 1000):
        if max_workers <= 0 or max_queue <= 0:
            raise ValueError("max_workers and max_queue must be positive")
        self.max_workers = max_workers
        self.max_queue = max_queue
        self._queue: list[_QueuedTask] = []
        self._queued_ids: set[str] = set()
        self._sequence = 0
        self._active = 0
        self._stopping = False
        self._condition = threading.Condition()

    def submit(self, task_id: str, fn: Callable[[], object], priority: int = 100) -> bool:
        with self._condition:
            if self._stopping:
                raise RuntimeError("scheduler is stopping")
            if task_id in self._queued_ids:
                return False
            if len(self._queue) >= self.max_queue:
                raise OverflowError("scheduler queue is full")
            self._sequence += 1
            heappush(self._queue, _QueuedTask(priority, self._sequence, task_id, fn))
            self._queued_ids.add(task_id)
            self._condition.notify()
            return True

    def run(self) -> list[object]:
        """Run queued tasks with at most max_workers threads."""
        results: list[object] = []
        threads: list[threading.Thread] = []

        def worker(task: _QueuedTask) -> None:
            try:
                result = task.fn()
                with self._condition:
                    results.append(result)
            finally:
                with self._condition:
                    self._active -= 1
                    self._condition.notify_all()

        while True:
            with self._condition:
                while self._queue and self._active < self.max_workers:
                    task = heappop(self._queue)
                    self._queued_ids.discard(task.task_id)
                    self._active += 1
                    thread = threading.Thread(target=worker, args=(task,), daemon=True)
                    threads.append(thread)
                    thread.start()
                if not self._queue and self._active == 0:
                    break
                self._condition.wait(timeout=0.05)
        for thread in threads:
            thread.join()
        return results

    def shutdown(self) -> None:
        with self._condition:
            self._stopping = True
            self._queue.clear()
            self._queued_ids.clear()
            self._condition.notify_all()

    @property
    def queued(self) -> int:
        with self._condition:
            return len(self._queue)

    @property
    def active(self) -> int:
        with self._condition:
            return self._active
