"""Release Automation Manager

Production release workflow foundation.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Release:
    version: str
    status: str = "pending"
    created_at: str = ""


class ReleaseAutomationManager:
    def __init__(self):
        self.releases = []

    def create_release(self, version: str):
        release = Release(
            version=version,
            created_at=datetime.utcnow().isoformat()
        )
        self.releases.append(release)
        return release

    def promote(self, release: Release):
        release.status = "production"
        return release

    def rollback(self, release: Release):
        release.status = "rollback"
        return release
