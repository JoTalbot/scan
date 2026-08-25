"""Intelligent Agent Scheduler Layer.

Provides task routing foundations for agent fleets.
"""

class IntelligentAgentScheduler:
    def __init__(self):
        self.queue = []
        self.agents = []

    def register_agent(self, agent):
        self.agents.append(agent)

    def submit_task(self, task):
        self.queue.append(task)

    def select_agent(self, task):
        for agent in self.agents:
            if hasattr(agent, "can_handle") and agent.can_handle(task):
                return agent
        return None

    def schedule(self):
        results = []
        for task in list(self.queue):
            agent = self.select_agent(task)
            if agent:
                results.append((task, agent))
                self.queue.remove(task)
        return results
