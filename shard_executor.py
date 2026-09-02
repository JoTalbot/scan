#!/usr/bin/env python3
"""Execute one pre-authorized shard with durable idempotency.

The caller owns target selection and authorization. This boundary only tracks
operational job/shard identifiers and executes the supplied command.
"""

import os
import subprocess

import job_state


def _required_context():
    job_id = os.environ.get("SCAN_JOB_ID", "").strip()
    authorization_ref = os.environ.get("SCAN_AUTHORIZATION_REF", "").strip()
    scope_ref = os.environ.get("SCAN_SCOPE_REF", "").strip()
    if not job_id:
        raise ValueError("SCAN_JOB_ID is required")
    if not authorization_ref:
        raise PermissionError("SCAN_AUTHORIZATION_REF is required")
    if not scope_ref:
        raise PermissionError("SCAN_SCOPE_REF is required")
    return job_id, authorization_ref, scope_ref


def execute_shard(shard_id, command, *, timeout=3600, state_path=None):
    """Return subprocess rc; completed shards are never executed twice."""
    if not isinstance(shard_id, str) or not shard_id.strip():
        raise ValueError("shard_id is required")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("command is required")

    job_id, authorization_ref, scope_ref = _required_context()
    state_path = state_path or job_state.DEFAULT_STATE_FILE
    job_state.start_job(
        job_id,
        authorization_ref=authorization_ref,
        scope_ref=scope_ref,
        state_path=state_path,
    )

    if job_state.shard_completed(job_id, shard_id, state_path=state_path):
        return 0

    result = subprocess.run(command, shell=True, timeout=timeout, check=False)
    if result.returncode == 0:
        job_state.mark_shard_completed(job_id, shard_id, state_path=state_path)
    return result.returncode
