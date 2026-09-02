import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_state_is_production_ready_and_points_to_maintenance():
    state = json.loads((ROOT / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    assert state["status"] == "production-ready"
    assert state["next_phase"] == "maintenance"
    assert not state["active_work"]
    assert state["backlog"]["p2_completed_in_observability"]
    assert state["backlog"]["security_completed_in_production_batch"]


def test_release_docs_exist():
    assert (ROOT / "docs" / "PRE_OBSERVABILITY_ARCHITECTURE.md").is_file()
    assert (ROOT / "docs" / "RELEASE_CHECKLIST.md").is_file()
    assert (ROOT / "docs" / "CHANGELOG_PRE_OBSERVABILITY.md").is_file()
    assert (ROOT / "docs" / "OBSERVABILITY.md").is_file()
