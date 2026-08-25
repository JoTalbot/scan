"""Global Agent Policy Engine.

Controls policy evaluation, versioning hooks, and approval requirements.
"""

class PolicyEngine:
    def __init__(self, policies=None):
        self.policies = policies or []

    def evaluate(self, action):
        for policy in self.policies:
            if not policy.get("enabled", True):
                continue
            if action.get("type") in policy.get("blocked_actions", []):
                return {"allowed": False, "reason": "blocked_by_policy"}
        return {"allowed": True}

    def add_policy(self, policy):
        self.policies.append(policy)
