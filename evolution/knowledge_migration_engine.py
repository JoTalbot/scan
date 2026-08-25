"""Knowledge Migration Engine.

Moves reusable skills and verified knowledge from retiring agents
into shared memory for active agents.
"""

from datetime import datetime


class KnowledgeMigrationEngine:
    def migrate(self, retiring_agent, target_agents, knowledge):
        return {
            "source": retiring_agent,
            "targets": target_agents,
            "knowledge": knowledge,
            "migrated_at": datetime.utcnow().isoformat(),
            "status": "completed"
        }

    def merge_skills(self, skills):
        return list(dict.fromkeys(skills))
