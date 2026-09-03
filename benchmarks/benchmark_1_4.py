#!/usr/bin/env python3
"""Repeatable offline performance smoke benchmarks, not a CI timing gate."""
from __future__ import annotations
import json, time
from detection_intelligence import classify_differential, normalize_vulnerability
from scheduler import deterministic_task_id

ITERATIONS = 2000

def run(iterations=ITERATIONS):
    cases = {
        "task_id": lambda: deterministic_task_id("job", "shard-1"),
        "diff": lambda: classify_differential("a", "a"),
        "vuln": lambda: normalize_vulnerability("vendor", "product", "1.0"),
    }
    result = {"iterations": iterations, "benchmarks": {}, "network": False}
    for name, fn in cases.items():
        started = time.perf_counter()
        for _ in range(iterations): fn()
        elapsed = time.perf_counter() - started
        result["benchmarks"][name] = {"total_ms": round(elapsed * 1000, 3),
                                       "ops_per_second": round(iterations / elapsed, 2) if elapsed else None}
    return result

if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
