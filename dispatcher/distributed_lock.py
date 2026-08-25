"""Distributed lock manager for multi-agent coordination."""

import time

LOCKS = {}


def acquire_lock(resource, agent_id, timeout=300):
    now = time.time()
    lock = LOCKS.get(resource)
    if lock and now - lock["time"] < timeout:
        return False
    LOCKS[resource] = {"agent": agent_id, "time": now}
    return True


def release_lock(resource, agent_id):
    lock = LOCKS.get(resource)
    if lock and lock["agent"] == agent_id:
        del LOCKS[resource]
        return True
    return False
