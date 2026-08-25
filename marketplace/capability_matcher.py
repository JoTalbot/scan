"""
Capability Matcher

Selects agents based on task requirements and registered capabilities.
"""

import json
from pathlib import Path


REGISTRY = Path("marketplace/capability_registry.json")


def load_registry():
    if not REGISTRY.exists():
        return {"agents": [], "capabilities": [], "reputation": []}
    return json.loads(REGISTRY.read_text())


def match(task_capabilities):
    registry = load_registry()
    matches = []
    for agent in registry.get("agents", []):
        score = len(set(task_capabilities) & set(agent.get("capabilities", [])))
        if score:
            matches.append({"agent": agent.get("id"), "score": score})
    return sorted(matches, key=lambda x: x["score"], reverse=True)
