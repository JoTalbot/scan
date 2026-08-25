"""Context retrieval layer for autonomous agents."""

import json
from pathlib import Path


class ContextRetrieval:
    def __init__(self, index_path="memory/memory_index.json"):
        self.index_path = Path(index_path)

    def load(self):
        if not self.index_path.exists():
            return {}
        return json.loads(self.index_path.read_text())

    def retrieve(self, query):
        memory = self.load()
        results = []
        text = query.lower()
        for layer, items in memory.get("layers", {}).items():
            for item in items:
                if text in str(item).lower():
                    results.append({"layer": layer, "item": item})
        return results
