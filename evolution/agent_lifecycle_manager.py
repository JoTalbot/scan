"""Agent Lifecycle Manager

Manages lifecycle states:
spawn -> train -> active -> upgrade -> retire
"""

class AgentLifecycleManager:
    STATES = ["spawn", "training", "active", "upgrade", "retired"]

    def transition(self, agent, new_state):
        if new_state not in self.STATES:
            raise ValueError("Unknown lifecycle state")
        agent["state"] = new_state
        return agent

    def retire(self, agent):
        return self.transition(agent, "retired")

    def upgrade(self, agent):
        return self.transition(agent, "upgrade")
