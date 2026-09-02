from report_sanitize import public_finding, target_id


def test_public_finding_removes_sensitive_fields():
    result = public_finding(
        {
            "ip": "192.0.2.10",
            "vendor": "Example",
            "username": "admin",
            "password": "super-secret",
            "auth_method": "basic",
        },
        salt="test-only",
    )
    assert result["target_id"] == target_id("192.0.2.10", "test-only")
    assert "ip" not in result
    assert "username" not in result
    assert "password" not in result
    assert "super-secret" not in repr(result)
    assert result["credential_class"] == "verified-credential"


def test_public_finding_redacts_secret_like_keys():
    result = public_finding(
        {"vendor": "Example", "api_key": "secret", "cookie": "session-value"},
        salt="test-only",
    )
    assert "secret" not in repr(result)
    assert "session-value" not in repr(result)
    assert "api_key" not in result
    assert "cookie" not in result
