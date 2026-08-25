"""
Agent Reputation Scoring

Tracks effectiveness of agents from verified task outcomes.
"""


def calculate(successes, failures):
    total = successes + failures
    if total == 0:
        return 0.0
    return round(successes / total, 3)


def update(record, success):
    record.setdefault("successes", 0)
    record.setdefault("failures", 0)
    if success:
        record["successes"] += 1
    else:
        record["failures"] += 1
    record["score"] = calculate(record["successes"], record["failures"])
    return record
