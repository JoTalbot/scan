#!/usr/bin/env python3
"""Small orchestration adapter for durable, idempotent job steps.

This module deliberately accepts an already-authorized command from the caller.
It does not discover targets, credentials, or authorization and stores only
operational completion metadata.
"""

import os
import subprocess

import job_state


class AuthorizationError(PermissionError):
    pass


def require_job_context():
    authorization_ref = os.environ.get("SCAN_AUTHORIZATION_REF", "").strip()
    scope_ref = os.environ.get("SCAN_SCOPE_REF", "").strip()
    job_id = os.environ.get("SCAN_JOB_ID", "").strip()
    if not authorization_ref:
        raise AuthorizationError("SCAN_AUTHORIZATION_REF is required")
    if not scope_ref:
        raise AuthorizationError("SCAN_SCOPE_REF is required")
    if not job_id:
        raise ValueError("SCAN_JOB_ID is required")
    return job_id, authorization_ref, scope_ref


def run_step(step, command, *, timeout=3600, state_path=None):
    """Run an authorized step once; mark it complete only when rc == 0."""
    if not step or not isinstance(step, str):
        raise ValueError("step is required")
    if not command or not isinstance(command, str):
        raise ValueError("command is required")

    job_id, authorization_ref, scope_ref = require_job_context()
    state_path = state_path or job_state.DEFAULT_STATE_FILE
    job_state.start_job(
        job_id,
        authorization_ref=authorization_ref,
        scope_ref=scope_ref,
        state_path=state_path,
    )
    if job_state.step_completed(job_id, step, state_path=state_path):
        return 0

    result = subprocess.run(command, shell=True, timeout=timeout, check=False)
    if result.returncode == 0:
        job_state.mark_step(job_id, step, state_path=state_path)
    return result.returncode
