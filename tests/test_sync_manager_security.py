import gzip
import sqlite3

import sync_manager


def test_credential_export_contains_no_credential_material(tmp_path, monkeypatch):
    db = tmp_path / "scan.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE router_credentials (
        id INTEGER PRIMARY KEY, ip TEXT, port INTEGER, vendor TEXT, model TEXT,
        device_type TEXT, username TEXT, password TEXT, auth_method TEXT,
        http_status INTEGER, realm TEXT, checked_at TEXT
    )""")
    conn.executemany(
        "INSERT INTO router_credentials(ip, vendor, username, password, auth_method) VALUES (?, ?, ?, ?, ?)",
        [("192.0.2.10", "ExampleRouter", "admin", "secret", "http-basic"),
         ("192.0.2.11", "ExampleRouter", "root", "another-secret", "http-basic")],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(sync_manager, "DB_FILE", str(db))
    monkeypatch.setattr(sync_manager, "BASE_DIR", str(tmp_path))
    path = sync_manager.export_credentials("test")
    assert path is not None
    text = gzip.open(path, "rt", encoding="utf-8").read().lower()
    assert "password" not in text
    assert "username" not in text
    assert "secret" not in text
    assert "192.0.2.10" not in text
    assert "examplerouter" in text
    assert "http-basic" in text
