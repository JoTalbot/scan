#!/usr/bin/env python3
"""Fail-closed authorization gate for active security operations."""

import os


def authorization_ref(env=None):
    """Return the operator-supplied authorization reference, if present."""
    env = os.environ if env is None else env
    value = str(env.get("SCAN_AUTHORIZATION_REF", "")).strip()
    return value or None


def require_authorization(env=None):
    """Require an explicit authorization reference before active operations."""
    ref = authorization_ref(env)
    if not ref:
        raise PermissionError(
            "Active operation blocked: SCAN_AUTHORIZATION_REF is required."
        )
    return ref


def is_authorized(env=None):
    return authorization_ref(env) is not None
