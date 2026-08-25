"""SLA and priority management layer for agent scheduling."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TaskPriority:
    task_id: str
    priority: int
    deadline: datetime | None = None


class SLAPriorityManager:
    def __init__(self):
        self.tasks = {}

    def register_task(self, task: TaskPriority):
        self.tasks[task.task_id] = task

    def get_priority(self, task_id: str):
        task = self.tasks.get(task_id)
        return task.priority if task else None

    def check_deadline(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task or not task.deadline:
            return False
        return datetime.utcnow() >= task.deadline
