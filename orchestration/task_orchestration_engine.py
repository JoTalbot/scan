"""Task Orchestration Intelligence Layer.

Coordinates complex workflows, dependencies and parallel execution planning.
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class WorkflowTask:
    task_id: str
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"


class TaskOrchestrationEngine:
    def __init__(self):
        self.tasks: Dict[str, WorkflowTask] = {}

    def add_task(self, task: WorkflowTask):
        self.tasks[task.task_id] = task

    def ready_tasks(self):
        return [
            task for task in self.tasks.values()
            if task.status == "pending"
            and all(self.tasks.get(dep, WorkflowTask(dep)).status == "completed" for dep in task.dependencies)
        ]
