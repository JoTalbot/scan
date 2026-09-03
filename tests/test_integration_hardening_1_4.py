from integration_hardening import validate_pipeline
from historical_analytics import aggregate
from plugins import PluginInfo, compatible_version


def test_platform_pipeline_composes_bounded_primitives_without_target_data():
    result = validate_pipeline(
        profile_name="safe-default",
        finding_id="finding-1",
        detector_version="1.4.0",
        signal_sources=("server-header", "title"),
        probe_name="http",
        worker_id="worker-a",
        capabilities=("http",),
    )
    assert result["worker"] == "worker-a"
    assert result["differential_example"] == "NEW"
    assert result["profile_limits"]["max_ports"] <= 65535
    assert "target" not in str(result).lower()


def test_plugin_contract_versioning_is_major_compatible():
    assert compatible_version("1.9", "1.0")
    assert not compatible_version("2.0", "1.0")
    assert PluginInfo("demo", "1.2").validate().version == "1.2"


def test_historical_analytics_is_aggregate_only():
    events = [
        {"ts": "2026-09-03T10:10:00Z", "event": "job.completed", "duration_ms": 10},
        {"ts": "2026-09-03T10:20:00Z", "event": "job.failed", "duration_ms": 20},
    ]
    result = aggregate(events)
    bucket = result["2026-09-03T10:00:00Z"]
    assert bucket["count"] == 2
    assert bucket["failed"] == 1
    assert bucket["error_rate"] == 0.5
