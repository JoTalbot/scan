import sqlite3

import web_server


def test_dashboard_credential_endpoint_returns_aggregates_only():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE router_credentials (
            id INTEGER PRIMARY KEY,
            ip TEXT,
            vendor TEXT,
            username TEXT,
            password TEXT,
            auth_method TEXT,
            http_status INTEGER,
            checked_at TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO router_credentials(ip, vendor, username, password, auth_method, http_status, checked_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("192.0.2.10", "ExampleRouter", "admin", "secret", "http-basic", 200, "2026-09-02T20:00:00Z"),
            ("192.0.2.11", "ExampleRouter", "root", "another-secret", "http-basic", 200, "2026-09-02T20:01:00Z"),
        ],
    )
    conn.commit()

    handler = object.__new__(web_server.ISPHandler)
    handler.get_conn = lambda: conn

    result = handler.get_creds()

    assert result["credential_material"] is False
    assert result["count"] == 2
    assert result["creds"] == [{"vendor": "ExampleRouter", "auth_method": "http-basic", "count": 2}]
    forbidden = {"ip", "username", "password", "secret", "token", "cookie"}
    assert not forbidden.intersection(result.keys())
    assert not any(forbidden.intersection(item.keys()) for item in result["creds"])
