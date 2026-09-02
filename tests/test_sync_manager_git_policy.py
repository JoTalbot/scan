import subprocess

import pytest

import sync_manager


def test_sync_to_github_requires_explicit_non_main_branch(monkeypatch, tmp_path):
    monkeypatch.setattr(sync_manager, "BASE_DIR", str(tmp_path))
    monkeypatch.setenv("SCAN_SYNC_BRANCH", "main")
    with pytest.raises(RuntimeError, match="main/master"):
        sync_manager.sync_to_github("test")


def test_sync_to_github_rejects_unexpected_staged_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(sync_manager, "BASE_DIR", str(tmp_path))
    monkeypatch.setenv("SCAN_SYNC_BRANCH", "sync/public")

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:4] == ["git", "diff", "--cached", "--name-only"]:
            return subprocess.CompletedProcess(args, 0, stdout="data/scans/safe.csv.gz\nsecrets.txt\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(sync_manager.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Staging policy violation"):
        sync_manager.sync_to_github("test")

    assert ["git", "add", "--", "data/scans/", "data/routers/", "data/creds/", "STATUS.md"] in calls
    assert ["git", "reset", "--", "data/scans/safe.csv.gz", "secrets.txt"] in calls


def test_sync_to_github_uses_configured_branch_for_pull_and_push(monkeypatch, tmp_path):
    monkeypatch.setattr(sync_manager, "BASE_DIR", str(tmp_path))
    monkeypatch.setenv("SCAN_SYNC_BRANCH", "sync/public")

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:4] == ["git", "diff", "--cached", "--name-only"]:
            return subprocess.CompletedProcess(args, 0, stdout="STATUS.md\n", stderr="")
        if args[:2] == ["git", "commit"]:
            return subprocess.CompletedProcess(args, 0, stdout="[sync/public abc123] test\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(sync_manager.subprocess, "run", fake_run)
    sync_manager.sync_to_github("test")

    assert ["git", "pull", "--rebase", "origin", "sync/public"] in calls
    assert ["git", "push", "origin", "HEAD:sync/public"] in calls
