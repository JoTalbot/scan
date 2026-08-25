"""Security control layer for autonomous agents."""

class SecurityManager:
    def __init__(self):
        self.permissions = {}

    def register_agent(self, agent_id, permissions):
        self.permissions[agent_id] = permissions

    def check_permission(self, agent_id, action):
        return action in self.permissions.get(agent_id, [])
