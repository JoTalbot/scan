"""Agent Fleet Management Layer.

Manages agent groups, scheduling metadata and fleet state.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class AgentNode:
    agent_id: str
    capability: str
    status: str = "active"


class AgentFleetManager:
    def __init__(self):
        self.agents: Dict[str, AgentNode] = {}

    def register(self, agent: AgentNode):
        self.agents[agent.agent_id] = agent

    def available_agents(self) -> List[AgentNode]:
        return [a for a in self.agents.values() if a.status == "active"]

    def schedule(self, capability: str):
        return [a for a in self.available_agents() if a.capability == capability]
