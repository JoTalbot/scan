"""Autonomous Agent Spawner

Creates agent profiles when required capabilities are missing.
"""

import json
from pathlib import Path

REGISTRY = Path("marketplace/capability_registry.json")


def find_missing_capability(required):
    if not REGISTRY.exists():
        return required
    data = json.loads(REGISTRY.read_text())
    existing = {c.get("name") for c in data.get("capabilities", [])}
    return None if required in existing else required


def create_agent_profile(capability):
    return {
        "role": f"agent_{capability}",
        "capabilities": [capability],
        "status": "training"
    }
