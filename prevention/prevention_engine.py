"""
Prevention Engine
Turns repeated repair patterns into preventive checks.
"""

from collections import Counter


class PreventionEngine:
    def __init__(self, history=None):
        self.history = history or []

    def detect_patterns(self):
        return Counter(item.get("problem") for item in self.history)

    def create_rule(self, problem):
        return {
            "type": "preventive_check",
            "source": problem,
            "enabled": True
        }

    def generate_rules(self, threshold=3):
        rules = []
        for problem, count in self.detect_patterns().items():
            if problem and count >= threshold:
                rules.append(self.create_rule(problem))
        return rules
