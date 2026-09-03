#!/usr/bin/env python3
"""Bounded worker capabilities, health scoring and scheduler-compatible leases."""
from __future__ import annotations
from dataclasses import dataclass, field
from scheduler import LeaseRegistry

@dataclass
class Worker:
    worker_id: str
    capabilities: frozenset[str]
    success_count: int = 0
    failure_count: int = 0
    latency_ms: float = 0.0
    active: bool = True

    @property
    def health(self) -> float:
        total = self.success_count + self.failure_count
        reliability = 1.0 if total == 0 else self.success_count / total
        latency_factor = 1.0 if self.latency_ms <= 1000 else max(0.1, 1000.0 / self.latency_ms)
        return round(reliability * latency_factor, 4)

    def record(self, success: bool, latency_ms: float) -> None:
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.latency_ms = max(0.0, min(float(latency_ms), 60000.0))

@dataclass
class CapabilityRegistry:
    max_workers: int = 256
    workers: dict[str, Worker] = field(default_factory=dict)
    leases: LeaseRegistry = field(default_factory=LeaseRegistry)

    def register(self, worker: Worker) -> None:
        if len(self.workers) >= self.max_workers and worker.worker_id not in self.workers:
            raise OverflowError("worker registry is full")
        if not worker.worker_id or len(worker.capabilities) > 64:
            raise ValueError("invalid worker registration")
        self.workers[worker.worker_id] = worker

    def candidates(self, capability: str) -> list[Worker]:
        return sorted((w for w in self.workers.values() if w.active and capability in w.capabilities),
                      key=lambda w: (-w.health, w.worker_id))

    def acquire(self, task_id: str, capability: str, now=None):
        for worker in self.candidates(capability):
            try:
                return self.leases.acquire(task_id, worker.worker_id, now)
            except RuntimeError:
                continue
        raise RuntimeError("no healthy worker available")
