#!/usr/bin/env python3
"""Fail-closed compatibility entrypoint for browser authentication checks."""
from authorization import require_authorization
from router_auth_browser_legacy import *
import router_auth_browser_legacy as _legacy

if __name__ == "__main__":
    require_authorization()
    _legacy.main()
