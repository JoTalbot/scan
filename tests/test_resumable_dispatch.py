import os

import pytest

import resumable_dispatch


def test_dispatch_requires_authorization(monkeypatch, tmp_path):
    monkeypatch.delenv("SCAN_AUTHORIZATION_REF", raising=False)
    monkeypatch.setenv("SCAN_SCOPE_REF", "scope:test")
    with pytest.raises(PermissionError):
        resumable_dispatch.run_shard(
            "job-1", 0, 1, state_path=str(tmp_path / "state.json")
        )


def test_dispatch_requires_scope(monkeypatch, tmp_path):
    monkeypatch.setenv("SCAN_AUTHORIZATION_REF", "auth:test")
    monkeypatch.delenv("SCAN_SCOPE_REF", raising=False)
    with pytest.raises(ValueError, match="SCAN_SCOPE_REF"):
        resumable_dispatch.run_shard(
            "job-1", 0, 1, state_path=str(tmp_path / "state.json")
        )


def test_command_is_argv_based_and_bounded():
    argv = resumable_dispatch.build_scan_command(100, 0, 4, "80,8080", 100, 2.0)
    assert argv[argv.index("--concurrency") + 1] == "100"
    assert "--shard" in argv
    assert "--shard-total" in argv
    assert all(";" not in part and "&&" not in part for part in argv)


def test_concurrency_limit_is_enforced():
    with pytest.raises(ValueError, match="exceeds"):
        resumable_dispatch._bounded_concurrency(501, 500)


def test_invalid_ports_are_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("SCAN_AUTHORIZATION_REF", "auth:test")
    monkeypatch.setenv("SCAN_SCOPE_REF", "scope:test")
    with pytest.raises(ValueError, match="ports"):
        resumable_dispatch.run_shard(
            "job-1", 0, 1, ports="80,not-a-port",
            state_path=str(tmp_path / "state.json"),
        )
