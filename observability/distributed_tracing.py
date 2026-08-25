"""Distributed tracing foundation for agent execution flows."""

from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class TraceEvent:
    trace_id: str
    component: str
    action: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class DistributedTracer:
    def __init__(self):
        self.events = []

    def start_trace(self, component: str, action: str):
        trace_id = str(uuid.uuid4())
        self.events.append(TraceEvent(trace_id, component, action))
        return trace_id

    def add_event(self, trace_id: str, component: str, action: str):
        self.events.append(TraceEvent(trace_id, component, action))

    def get_trace(self, trace_id: str):
        return [e for e in self.events if e.trace_id == trace_id]
