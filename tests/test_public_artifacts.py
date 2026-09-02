from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_artifacts_contain_no_sensitive_field_values():
    for relative in ("README.md", "REPORT.md", "CVE_REPORT.md"):
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        assert "username,password" not in text
        assert "password=" not in text
        assert "passwd=" not in text
        assert "data/creds/" not in text
