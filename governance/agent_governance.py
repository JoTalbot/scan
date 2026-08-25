"""Agent Governance Layer.

Controls policies, approvals and audit events for autonomous agents.
"""

from datetime import datetime


class AgentGovernance:
    def __init__(self):
        self.audit_log = []
        self.policies = {}

    def register_policy(self, name, value):
        self.policies[name] = value

    def audit(self, agent, action, result):
        self.audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent,
            "action": action,
            "result": result,
        })

    def requires_approval(self, action):
        return self.policies.get(action, False)
