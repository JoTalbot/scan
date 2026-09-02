import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_state_is_observability_and_points_to_next_phase():
    state = json.loads((ROOT / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    assert state["status"] == "observability"
    assert state["next_phase"] == "documentation-and-release"
    assert not state["active_work"]
    assert state["backlog"]["p2_completed_in_observability"]


def test_release_docs_exist():
    assert (ROOT / "docs" / "PRE_OBSERVABILITY_ARCHITECTURE.md").is_file()
    assert (ROOT / "docs" / "RELEASE_CHECKLIST.md").is_file()
    assert (ROOT / "docs" / "CHANGELOG_PRE_OBSERVABILITY.md").is_file()
    assert (ROOT / "docs" / "OBSERVABILITY.md").is_file()
