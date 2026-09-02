#!/usr/bin/env python3
"""Secure entrypoint for the RouterScan dashboard."""
import json
import os
import statistics
from collections import Counter
import web_server_legacy as _legacy
from report_sanitize import target_id
from web_server_legacy import *  # noqa: F401,F403,E402


def _public_target_id(value):
    salt = os.environ.get("SCAN_PUBLIC_ID_SALT", "")
    return target_id(str(value), salt) if salt else None


def _safe_get_creds(self):
    """Return aggregate audit metadata only, never credential material."""
    conn = self.get_conn()
    rows = conn.execute("""
        SELECT vendor, auth_method, COUNT(*) AS count
        FROM router_credentials GROUP BY vendor, auth_method
        ORDER BY count DESC, vendor LIMIT 200
    """).fetchall()
    conn.close()
    return {"count": sum(r["count"] for r in rows), "credential_material": False,
            "creds": [dict(r) for r in rows]}


def _safe_get_routers(self, limit=100):
    """Return router audit metadata without live IP addresses."""
    conn = self.get_conn()
    rows = conn.execute("""
        SELECT ip, vendor, model, device_type, confidence, matched_on,
               auth_result, browser_result, extra_ports
        FROM scan_routers ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    routers = []
    for r in rows:
        item = {"vendor": r["vendor"], "model": r["model"], "device_type": r["device_type"],
                "confidence": r["confidence"], "matched_on": r["matched_on"],
                "auth_result": r["auth_result"], "browser_result": r["browser_result"],
                "extra_ports": r["extra_ports"]}
        public_id = _public_target_id(r["ip"])
        if public_id:
            item["target_id"] = public_id
        routers.append(item)
    return {"count": len(routers), "routers": routers}


def _read_telemetry(path):
    """Read bounded aggregate telemetry without returning raw event records."""
    counts = Counter()
    durations = []
    detections = Counter()
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                event = str(row.get("event", "unknown"))[:96]
                counts[event] += 1
                duration = row.get("duration_ms")
                if isinstance(duration, (int, float)) and duration >= 0:
                    durations.append(float(duration))
                if event == "detection.result":
                    vendor = str(row.get("vendor", "unknown"))[:96]
                    detections[vendor] += 1
    except (OSError, ValueError, TypeError):
        return None
    return counts, durations, detections


def _safe_get_observability(self):
    """Return aggregated telemetry state, never raw events or sensitive values."""
    path = os.environ.get("SCAN_OBSERVABILITY_FILE", "")
    if not path or not os.path.exists(path):
        return {"enabled": False, "events": 0, "event_types": {}}
    data = _read_telemetry(path)
    if data is None:
        return {"enabled": True, "events": 0, "event_types": {}, "read_error": True}
    counts, _, _ = data
    return {"enabled": True, "events": sum(counts.values()), "event_types": dict(sorted(counts.items()))}


def _safe_get_observability_metrics(self):
    """Return chart-ready aggregate metrics with no targets or raw telemetry."""
    path = os.environ.get("SCAN_OBSERVABILITY_FILE", "")
    if not path or not os.path.exists(path):
        return {"enabled": False, "jobs": {}, "shards": {}, "detections": {}, "duration_ms": {}}
    data = _read_telemetry(path)
    if data is None:
        return {"enabled": True, "read_error": True}
    counts, durations, detections = data
    job_completed = counts.get("job.completed", 0)
    job_failed = counts.get("job.failed", 0)
    shard_completed = counts.get("shard.completed", 0)
    shard_failed = counts.get("shard.failed", 0)
    shard_retried = counts.get("shard.retry", 0) + counts.get("shard.retried", 0)
    return {
        "enabled": True,
        "jobs": {"completed": job_completed, "failed": job_failed,
                 "total_terminal": job_completed + job_failed,
                 "failure_rate": (job_failed / (job_completed + job_failed)) if job_completed + job_failed else 0.0},
        "shards": {"completed": shard_completed, "failed": shard_failed, "retried": shard_retried,
                   "failure_rate": (shard_failed / (shard_completed + shard_failed)) if shard_completed + shard_failed else 0.0},
        "detections": {"total": counts.get("detection.result", 0), "by_vendor": dict(detections.most_common(20))},
        "duration_ms": {
            "count": len(durations),
            "mean": statistics.fmean(durations) if durations else 0.0,
            "max": max(durations) if durations else 0.0,
        },
    }


_legacy.ISPHandler.get_creds = _safe_get_creds
_legacy.ISPHandler.get_routers = _safe_get_routers
_legacy.ISPHandler.get_observability = _safe_get_observability
_legacy.ISPHandler.get_observability_metrics = _safe_get_observability_metrics
ISPHandler.get_creds = _safe_get_creds
ISPHandler.get_routers = _safe_get_routers
ISPHandler.get_observability = _safe_get_observability
ISPHandler.get_observability_metrics = _safe_get_observability_metrics

_original_do_get = _legacy.ISPHandler.do_GET


def _secure_do_get(self):
    path = self.path.split("?", 1)[0]
    if path == "/api/observability":
        self.send_json(self.get_observability())
        return
    if path == "/api/observability/metrics":
        self.send_json(self.get_observability_metrics())
        return
    _original_do_get(self)


_legacy.ISPHandler.do_GET = _secure_do_get
ISPHandler.do_GET = _secure_do_get

if __name__ == "__main__":
    _legacy.run()
