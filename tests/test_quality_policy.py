import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_state_is_pre_observability_and_points_to_next_phase():
    state = json.loads((ROOT / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    assert state["status"] == "pre-observability"
    assert state["next_phase"] == "observability"
    assert not state["active_work"]
    assert state["backlog"]["p1_completed_in_batch"]


def test_release_docs_exist():
    assert (ROOT / "docs" / "PRE_OBSERVABILITY_ARCHITECTURE.md").is_file()
    assert (ROOT / "docs" / "RELEASE_CHECKLIST.md").is_file()
    assert (ROOT / "docs" / "CHANGELOG_PRE_OBSERVABILITY.md").is_file()
