from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_public_artifacts_contain_no_sensitive_field_values():
    for relative in ("README.md", "REPORT.md", "CVE_REPORT.md", "STATUS.md"):
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        assert "username,password" not in text
        assert "password=" not in text
        assert "passwd=" not in text
        assert "data/creds/" not in text
        assert "verified:admin:" not in text


def test_public_report_does_not_contain_ipv4_targets():
    text = (ROOT / "REPORT.md").read_text(encoding="utf-8", errors="ignore")
    assert not re.search(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])", text)


def test_public_status_contains_no_live_operational_targets():
    text = (ROOT / "STATUS.md").read_text(encoding="utf-8", errors="ignore").lower()
    for marker in (
        "authorization_ref",
        "scope_ref",
        "target_inventory",
        "live_target",
        "raw_http",
        "data/creds/",
    ):
        assert marker not in text
