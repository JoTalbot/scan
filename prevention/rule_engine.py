"""Preventive rule engine.

Converts learned patterns into future scan checks.
"""

import json
from pathlib import Path


class RuleEngine:
    def __init__(self, registry="prevention/rule_registry.json"):
        self.registry = Path(registry)

    def load_rules(self):
        if not self.registry.exists():
            return []
        return json.loads(self.registry.read_text()).get("rules", [])

    def add_rule(self, rule):
        data = {"rules": self.load_rules()}
        data["rules"].append(rule)
        self.registry.write_text(json.dumps(data, indent=2))

    def apply(self, scan_context):
        return [r for r in self.load_rules() if r.get("match") in scan_context]
