import os
import subprocess
import sys

import pytest

import authorization


def test_authorization_gate_is_fail_closed():
    with pytest.raises(PermissionError):
        authorization.require_authorization({})


def test_authorization_gate_accepts_explicit_reference():
    assert authorization.require_authorization({"SCAN_AUTHORIZATION_REF": "job-123"}) == "job-123"


def test_auth_checker_entrypoint_blocks_without_authorization():
    env = dict(os.environ)
    env.pop("SCAN_AUTHORIZATION_REF", None)
    result = subprocess.run(
        [sys.executable, "router_auth_check.py", "--dry-run"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "SCAN_AUTHORIZATION_REF" in (result.stderr + result.stdout)
