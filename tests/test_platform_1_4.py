from evidence import EvidenceItem, EvidenceSignal, build_evidence
from scan_profiles import DEFAULT_SAFE_PROFILE, get_profile
from agent_registry import CapabilityRegistry, Worker
from plugins import PluginInfo, compatible_version, validate_metadata
from historical_analytics import aggregate


def test_evidence_is_stable_and_does_not_store_raw_values():
    signal = EvidenceSignal("server_header", "matched", "1.4.0", 0.9)
    item = build_evidence("finding-1", "http", "1.0", "1.4.0", [signal])[0]
    assert item.evidence_id == EvidenceItem("finding-1", signal, "http", "1.0", "scanner").evidence_id
    assert "raw-target" not in str(item.to_dict())


def test_safe_profile_is_bounded():
    assert DEFAULT_SAFE_PROFILE.validate() == DEFAULT_SAFE_PROFILE
    assert get_profile().concurrency <= 500


def test_registry_selects_healthiest_capable_worker():
    registry = CapabilityRegistry()
    weak = Worker("b", frozenset({"http"}), failure_count=2)
    strong = Worker("a", frozenset({"http"}), success_count=2)
    registry.register(weak); registry.register(strong)
    lease = registry.acquire("task", "http", now=10.0)
    assert lease.worker_id == "a"


def test_plugins_are_major_version_compatible_and_bounded():
    assert compatible_version("1.2")
    assert not compatible_version("2.0")
    assert PluginInfo("demo", "1.0").validate().name == "demo"
    try:
        validate_metadata({"x": "y" * 257})
        assert False
    except ValueError:
        pass


def test_historical_analytics_aggregates_without_target_fields():
    events = [
        {"ts": "2026-09-03T10:01:00Z", "event": "scan.completed", "duration_ms": 10},
        {"ts": "2026-09-03T10:02:00Z", "event": "scan.failed", "duration_ms": 30, "target": "secret"},
    ]
    result = aggregate(events)
    row = result["2026-09-03T10:00:00Z"]
    assert row["count"] == 2 and row["failed"] == 1
    assert "target" not in str(result)
