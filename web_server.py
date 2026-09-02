#!/usr/bin/env python3
"""Secure entrypoint for the RouterScan dashboard.

The legacy dashboard implementation is kept intact in ``web_server_legacy``.
This wrapper prevents the public credential endpoint from exposing credential
material while preserving the existing dashboard behavior.
"""

import web_server_legacy as _legacy

# Re-export the existing public names for compatibility.
from web_server_legacy import *  # noqa: F401,F403,E402


def _safe_get_creds(self):
    """Return aggregate audit metadata only, never credential material."""
    conn = self.get_conn()
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT vendor, auth_method, COUNT(*) AS count
        FROM router_credentials
        GROUP BY vendor, auth_method
        ORDER BY count DESC, vendor
        LIMIT 200
        """
    ).fetchall()
    conn.close()
    return {
        "count": sum(r["count"] for r in rows),
        "credential_material": False,
        "creds": [dict(r) for r in rows],
    }


# The legacy run() resolves ISPHandler in its own module, so patch that class
# before delegating. This keeps the full dashboard intact without exposing the
# username/password columns from the legacy implementation.
_legacy.ISPHandler.get_creds = _safe_get_creds
ISPHandler.get_creds = _safe_get_creds


if __name__ == "__main__":
    _legacy.run()
