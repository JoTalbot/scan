"""Production metrics collector foundation for JoTalbot/scan.

Provides a minimal interface for collecting agent, task, and system metrics.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MetricEvent:
    name: str
    value: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class MetricsCollector:
    def __init__(self):
        self.events = []

    def record(self, name: str, value: float):
        self.events.append(MetricEvent(name, value))

    def get_metrics(self):
        return self.events
