"""Task priority engine.

Calculates execution priority for queued agent tasks.
"""


def calculate_priority(task):
    score = 0
    score += task.get("priority", 0)
    score += task.get("urgency", 0)
    if task.get("blocked", False):
        score -= 100
    return score


def sort_tasks(tasks):
    return sorted(tasks, key=calculate_priority, reverse=True)
