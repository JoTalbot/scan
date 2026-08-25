"""Agent Audit Analyzer.

Analyzes governance events and prepares recommendations.
"""

from collections import Counter


class AgentAuditAnalyzer:
    def analyze(self, audit_events):
        issues = []
        failures = Counter()

        for event in audit_events:
            if event.get("status") == "failed":
                failures[event.get("agent", "unknown")] += 1

        for agent, count in failures.items():
            issues.append({"agent": agent, "failures": count})

        return {"issues": issues, "recommendations": self.recommend(issues)}

    def recommend(self, issues):
        return [
            f"Review capability profile for {item['agent']}"
            for item in issues
        ]
