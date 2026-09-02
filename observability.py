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
    r"(?:token|secret|password|passwd|authorization|auth|credential|api[_-]?key|private[_-]?key|target|inventory|header|scope(?:[_-]?ref)?)",
    re.IGNORECASE,
)
_DEFAULT_MAX_BYTES = 5 * 1024 * 1024
_DEFAULT_ROTATIONS = 3


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
    """Bounded append-only JSONL sink with size-based rotation."""

    def __init__(self, path=None, max_bytes=None, rotations=None):
        configured = path or os.environ.get("SCAN_OBSERVABILITY_FILE", "")
        self.path = Path(configured) if configured else None
        self.max_bytes = self._positive_int(
            max_bytes if max_bytes is not None else os.environ.get("SCAN_OBSERVABILITY_MAX_BYTES"),
            _DEFAULT_MAX_BYTES,
        )
        self.rotations = self._bounded_int(
            rotations if rotations is not None else os.environ.get("SCAN_OBSERVABILITY_ROTATIONS"),
            _DEFAULT_ROTATIONS,
            minimum=0,
            maximum=20,
        )

    @staticmethod
    def _positive_int(value, default):
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    @classmethod
    def _bounded_int(cls, value, default, *, minimum, maximum):
        parsed = cls._positive_int(value, default)
        return max(minimum, min(parsed, maximum))

    def _rotate(self):
        if not self.path or self.rotations <= 0 or not self.path.exists():
            return
        for index in range(self.rotations, 0, -1):
            source = self.path.with_name(f"{self.path.name}.{index - 1}") if index > 1 else self.path
            destination = self.path.with_name(f"{self.path.name}.{index}")
            if destination.exists():
                destination.unlink()
            if source.exists():
                source.replace(destination)

    def _ensure_capacity(self, incoming_bytes):
        if not self.path or not self.path.exists() or self.max_bytes <= 0:
            return
        try:
            current = self.path.stat().st_size
        except OSError:
            return
        if current and current + incoming_bytes > self.max_bytes:
            self._rotate()

    def emit(self, event, **fields):
        if not self.path:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "event": safe_id(event),
        }
        payload.update(sanitize(fields))
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        encoded = line.encode("utf-8")
        self._ensure_capacity(len(encoded))
        try:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            # Telemetry is best-effort and must never alter scan behavior.
            return None
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
