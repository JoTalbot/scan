from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_artifacts_do_not_reference_plaintext_credential_exports():
    for relative in ("README.md", "STATUS.md", "REPORT.md", "CVE_REPORT.md"):
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        assert "router_credentials_" not in text
        assert "password," not in text


def test_security_policy_exists_and_requires_authorization():
    policy = (ROOT / "SECURITY_POLICY.md").read_text(encoding="utf-8")
    assert "explicitly authorized" in policy
    assert "fail closed" in policy.lower()
    assert "plaintext" in policy.lower()
