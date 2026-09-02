#!/usr/bin/env python3
"""Fail-closed compatibility entrypoint for router authentication checks."""
from authorization import require_authorization
from router_auth_check_legacy import *
import router_auth_check_legacy as _legacy

# Preserve the legacy module's private API helpers for existing callers/tests.
_api_encode_word = _legacy._api_encode_word
_api_encode_sentence = _legacy._api_encode_sentence

if __name__ == "__main__":
    require_authorization()
    _legacy.main()
