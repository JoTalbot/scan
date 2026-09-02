import os
import sys

import pytest

import dispatch


def test_dispatch_scan_requires_authorization(monkeypatch):
    monkeypatch.delenv("SCAN_AUTHORIZATION_REF", raising=False)
    monkeypatch.setenv("SCAN_SCOPE_REF", "scope:test")
    with pytest.raises(PermissionError):
        dispatch.dispatch_scan(1, 10, "80", False)


def test_scan_argv_uses_resumable_executor(monkeypatch):
    monkeypatch.setenv("SCAN_AUTHORIZATION_REF", "auth:test")
    monkeypatch.setenv("SCAN_SCOPE_REF", "scope:test")
    argv = dispatch._scan_argv("job-1", 2, 4, 1000, "80,443", 100, 500, 2.0)
    assert argv[1].endswith("resumable_dispatch.py")
    assert "--authorization-ref" in argv
    assert "auth:test" in argv
    assert "--scope-ref" in argv
    assert "scope:test" in argv
    assert "--concurrency" in argv
    assert "100" in argv
    assert "1000" in argv


def test_dispatch_rejects_unbounded_concurrency(monkeypatch):
    monkeypatch.setenv("SCAN_AUTHORIZATION_REF", "auth:test")
    monkeypatch.setenv("SCAN_SCOPE_REF", "scope:test")
    monkeypatch.setenv("SCAN_CONCURRENCY", "501")
    monkeypatch.setenv("SCAN_MAX_CONCURRENCY", "500")
    with pytest.raises(ValueError, match="concurrency exceeds"):
        dispatch.dispatch_scan(1, 10, "80", False)
