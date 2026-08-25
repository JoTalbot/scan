"""Knowledge Graph Intelligence Layer.

Provides a lightweight foundation for linking agents, tasks,
solutions and learned knowledge.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class KnowledgeNode:
    node_id: str
    node_type: str
    metadata: Dict[str, str] = field(default_factory=dict)


class KnowledgeGraphEngine:
    def __init__(self):
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: Dict[str, List[str]] = {}

    def add_node(self, node: KnowledgeNode):
        self.nodes[node.node_id] = node

    def link(self, source: str, target: str):
        self.edges.setdefault(source, []).append(target)

    def related(self, node_id: str) -> List[str]:
        return self.edges.get(node_id, [])
