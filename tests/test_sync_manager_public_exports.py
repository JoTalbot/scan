import csv
import gzip
import os
import sqlite3


def _load_rows(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def _db(tmp_path):
    path = tmp_path / "isp_cidr.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE scan_results (
            id INTEGER PRIMARY KEY, ip TEXT, port INTEGER, http_status INTEGER,
            server_header TEXT, title TEXT, asn INTEGER, isp_name TEXT,
            country_code TEXT, country_name_ru TEXT, response_time_ms REAL,
            scanned_at TEXT, has_banner INTEGER
        );
        CREATE TABLE scan_routers (
            id INTEGER PRIMARY KEY, ip TEXT, port INTEGER, http_status INTEGER,
            vendor TEXT, model TEXT, device_type TEXT, confidence REAL,
            matched_on TEXT, server_header TEXT, title TEXT, asn INTEGER,
            isp_name TEXT, country_code TEXT, country_name_ru TEXT, detected_at TEXT
        );
        CREATE TABLE router_credentials (
            ip TEXT, port INTEGER, vendor TEXT, model TEXT, device_type TEXT,
            username TEXT, password TEXT, auth_method TEXT, http_status INTEGER,
            realm TEXT, checked_at TEXT
        );
        INSERT INTO scan_results VALUES
          (1,'203.0.113.10',80,200,'Example','Router',64500,'ISP','UA','Ukraine',12.3,'2026-09-02',1);
        INSERT INTO scan_routers VALUES
          (1,'203.0.113.10',80,200,'Example','Model-X','router',0.9,'banner','Example','Router',64500,'ISP','UA','Ukraine','2026-09-02');
        INSERT INTO router_credentials VALUES
          ('203.0.113.10',80,'Example','Model-X','router','admin','not-a-real-secret','http-basic',200,'realm','2026-09-02');
        """
    )
    conn.commit()
    conn.close()
    return path


def test_public_exports_do_not_write_exact_ips_or_credentials(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr("sync_manager.DB_FILE", str(db))
    monkeypatch.setattr("sync_manager.SCANS_DIR", str(tmp_path / "scans"))
    monkeypatch.setenv("SCAN_PUBLIC_ID_SALT", "test-salt")

    import sync_manager

    scan_path = sync_manager.export_and_compress_scans("test")
    router_path = sync_manager.export_routers("test")
    cred_path = sync_manager.export_credentials("test")

    scan_text = "\n".join(",".join(row) for row in _load_rows(scan_path))
    router_text = "\n".join(",".join(row) for row in _load_rows(router_path))
    cred_text = "\n".join(",".join(row) for row in _load_rows(cred_path))

    for text in (scan_text, router_text, cred_text):
        assert "203.0.113.10" not in text
        assert "admin" not in text
        assert "not-a-real-secret" not in text
        assert "password" not in text.lower()

    assert _load_rows(scan_path)[0][0] == "Target_ID"
    assert _load_rows(router_path)[0][0] == "Target_ID"
    assert _load_rows(cred_path)[0] == ["Vendor", "Auth_Method", "Count"]


def test_public_exports_fail_closed_without_salt(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr("sync_manager.DB_FILE", str(db))
    monkeypatch.setattr("sync_manager.SCANS_DIR", str(tmp_path / "scans"))
    monkeypatch.delenv("SCAN_PUBLIC_ID_SALT", raising=False)

    import pytest
    import sync_manager

    with pytest.raises(RuntimeError, match="SCAN_PUBLIC_ID_SALT"):
        sync_manager.export_and_compress_scans("test")
