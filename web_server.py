#!/usr/bin/env python3
"""Secure entrypoint for the RouterScan dashboard."""
import os
import web_server_legacy as _legacy
from report_sanitize import target_id
from web_server_legacy import *  # noqa: F401,F403,E402


def _public_target_id(value):
    salt = os.environ.get("SCAN_PUBLIC_ID_SALT", "")
    return target_id(str(value), salt) if salt else None


def _safe_get_creds(self):
    """Return aggregate audit metadata only, never credential material."""
    conn = self.get_conn()
    rows = conn.execute("""
        SELECT vendor, auth_method, COUNT(*) AS count
        FROM router_credentials
        GROUP BY vendor, auth_method
        ORDER BY count DESC, vendor LIMIT 200
    """).fetchall()
    conn.close()
    return {"count": sum(r["count"] for r in rows), "credential_material": False,
            "creds": [dict(r) for r in rows]}


def _safe_get_routers(self, limit=100):
    """Return router audit metadata without live IP addresses."""
    conn = self.get_conn()
    rows = conn.execute("""
        SELECT ip, vendor, model, device_type, confidence, matched_on,
               auth_result, browser_result, extra_ports
        FROM scan_routers ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    routers = []
    for r in rows:
        item = {"vendor": r["vendor"], "model": r["model"],
                "device_type": r["device_type"], "confidence": r["confidence"],
                "matched_on": r["matched_on"], "auth_result": r["auth_result"],
                "browser_result": r["browser_result"], "extra_ports": r["extra_ports"]}
        public_id = _public_target_id(r["ip"])
        if public_id:
            item["target_id"] = public_id
        routers.append(item)
    return {"count": len(routers), "routers": routers}


_legacy.ISPHandler.get_creds = _safe_get_creds
_legacy.ISPHandler.get_routers = _safe_get_routers
ISPHandler.get_creds = _safe_get_creds
ISPHandler.get_routers = _safe_get_routers

if __name__ == "__main__":
    _legacy.run()
