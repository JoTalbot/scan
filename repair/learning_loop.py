"""Repair learning loop.

Connects repair outcomes with memory and future prevention.
"""


def record_repair_result(task_id, success, details=None):
    return {
        "task_id": task_id,
        "success": success,
        "details": details or {},
    }


def should_create_prevention_rule(history):
    return len(history) >= 3
