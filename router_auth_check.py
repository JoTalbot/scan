#!/usr/bin/env python3
"""Fail-closed compatibility entrypoint for router authentication checks."""
from authorization import require_authorization
from router_auth_check_legacy import *
import router_auth_check_legacy as _legacy

if __name__ == "__main__":
    require_authorization()
    _legacy.main()
