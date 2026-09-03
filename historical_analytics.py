#!/usr/bin/env python3
"""Bounded historical analytics over already-sanitized observability events."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone

def _bucket(ts: str, hour: bool = True) -> str:
    value = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    if hour:
        return value.strftime("%Y-%m-%dT%H:00:00Z")
    return value.strftime("%Y-%m-%dT00:00:00Z")

def aggregate(events, *, hour=True, max_events=10000):
    """Aggregate count, failures and bounded latency percentiles, never targets."""
    buckets = defaultdict(lambda: {"count": 0, "failed": 0, "durations": []})
    for index, event in enumerate(events):
        if index >= max_events:
            break
        if not isinstance(event, dict) or "ts" not in event or "event" not in event:
            continue
        try: key = _bucket(str(event["ts"]), hour)
        except (TypeError, ValueError): continue
        item = buckets[key]; item["count"] += 1
        if str(event["event"]).endswith(".failed"): item["failed"] += 1
        duration = event.get("duration_ms")
        if isinstance(duration, (int, float)) and 0 <= duration <= 60000 and len(item["durations"]) < 1000:
            item["durations"].append(float(duration))
    result = {}
    for key, item in sorted(buckets.items()):
        values = sorted(item["durations"])
        p50 = values[len(values)//2] if values else None
        result[key] = {"count": item["count"], "failed": item["failed"],
                       "error_rate": round(item["failed"] / item["count"], 4), "p50_duration_ms": p50}
    return result
