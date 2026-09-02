#!/usr/bin/env python3
"""Small dependency-free privacy-safe observability layer for RouterScan."""

import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_MAX_STRING = 256
_SAFE_ID = re.compile(r"[^A-Za-z0-9_.:-]+")
_SENSITIVE_KEY = re.compile(
    r"(?:token|secret|password|passwd|authorization|auth|credential|api[_-]?key|private[_-]?key|target|inventory|header)",
    re.IGNORECASE,
)


def _clean_string(value):
    return str(value).replace("\r", " ").replace("\n", " ")[:_MAX_STRING]


def safe_id(value):
    """Return a bounded identifier suitable for telemetry labels."""
    return _SAFE_ID.sub("_", _clean_string(value)).strip("_")[:96] or "unknown"


def sanitize(value, *, key=""):
    """Recursively redact sensitive fields and bound telemetry payload size."""
    if _SENSITIVE_KEY.search(key or ""):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {safe_id(k): sanitize(v, key=k) for k, v in list(value.items())[:64]}
    if isinstance(value, (list, tuple, set)):
        return [sanitize(v) for v in list(value)[:64]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _clean_string(value) if isinstance(value, str) else value
    return _clean_string(value)


class JsonlSink:
    """Append-only JSONL sink. Telemetry is opt-in through SCAN_OBSERVABILITY_FILE."""

    def __init__(self, path=None):
        configured = path or os.environ.get("SCAN_OBSERVABILITY_FILE", "")
        self.path = Path(configured) if configured else None

    def emit(self, event, **fields):
        if not self.path:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "event": safe_id(event),
        }
        payload.update(sanitize(fields))
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return payload


_DEFAULT_SINK = JsonlSink()


def emit(event, **fields):
    """Emit one privacy-safe event when observability is configured."""
    return _DEFAULT_SINK.emit(event, **fields)


def record_detection(result):
    """Emit only safe detection metadata, never raw HTTP artifacts."""
    if not result:
        emit("detection.none")
        return None
    sources = result.get("matched_sources", [])
    return emit(
        "detection.result",
        vendor=result.get("vendor"),
        model=result.get("model"),
        device_type=result.get("device_type"),
        confidence=result.get("confidence"),
        score=result.get("score"),
        score_confidence=result.get("score_confidence"),
        matched_on=result.get("matched_on"),
        matched_sources=[safe_id(s) for s in sources],
        signal_count=len(result.get("signals", [])),
    )


@contextmanager
def timed(event, **fields):
    """Emit ``*.started`` and a terminal event with bounded duration metadata."""
    started = time.monotonic()
    emit(f"{event}.started", **fields)
    try:
        yield
    except Exception as exc:
        emit(f"{event}.failed", duration_ms=round((time.monotonic() - started) * 1000, 3),
             error_type=type(exc).__name__, **fields)
        raise
    else:
        emit(f"{event}.completed", duration_ms=round((time.monotonic() - started) * 1000, 3), **fields)
