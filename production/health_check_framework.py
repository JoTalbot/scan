"""Production health check framework."""

from dataclasses import dataclass


@dataclass
class HealthStatus:
    component: str
    healthy: bool
    message: str = ""


class HealthCheckFramework:
    def __init__(self):
        self.checks = []

    def register(self, check):
        self.checks.append(check)

    def run(self):
        return [check() for check in self.checks]
