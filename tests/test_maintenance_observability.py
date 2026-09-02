from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_maintenance_observability_policy_is_privacy_safe():
    text = (ROOT / "docs" / "MAINTENANCE_OBSERVABILITY.md").read_text(encoding="utf-8").lower()
    assert "raw targets" in text
    assert "credentials" in text
    assert "authorization" in text
    assert "http bodies" in text
    assert "bounded" in text
    assert "rotation" in text


def test_project_state_remains_maintenance_source_of_truth():
    text = (ROOT / "PROJECT_STATE.json").read_text(encoding="utf-8")
    assert '"version": "1.3.0"' in text
    assert '"status": "production-ready"' in text
    assert '"next_phase": "maintenance"' in text
