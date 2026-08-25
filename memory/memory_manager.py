"""
Memory Manager for JoTalbot/scan.

Provides a simple interface for retrieving and storing agent knowledge.
"""

import json
from pathlib import Path

INDEX = Path("memory/memory_index.json")


class MemoryManager:
    def __init__(self):
        INDEX.parent.mkdir(exist_ok=True)
        if not INDEX.exists():
            INDEX.write_text('{"layers":{"agent":[],"project":[],"skills":[]}}')

    def load(self):
        return json.loads(INDEX.read_text())

    def store(self, layer, item):
        data = self.load()
        data.setdefault("layers", {}).setdefault(layer, []).append(item)
        INDEX.write_text(json.dumps(data, indent=2))

    def search(self, term):
        data = self.load()
        result = []
        for layer in data.get("layers", {}).values():
            for item in layer:
                if term.lower() in json.dumps(item).lower():
                    result.append(item)
        return result
