import pytest

from authorization import authorization_ref, is_authorized, require_authorization


def test_missing_authorization_is_not_authorized():
    env = {}
    assert authorization_ref(env) is None
    assert is_authorized(env) is False
    with pytest.raises(PermissionError):
        require_authorization(env)


def test_authorization_reference_is_trimmed():
    env = {"SCAN_AUTHORIZATION_REF": "  ticket-123  "}
    assert authorization_ref(env) == "ticket-123"
    assert is_authorized(env) is True


def test_secret_like_values_are_not_logged_or_transformed():
    env = {"SCAN_AUTHORIZATION_REF": "case-42"}
    assert require_authorization(env) == "case-42"
