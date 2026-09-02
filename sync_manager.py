#!/usr/bin/env python3
"""
Storage Scaling & Auto-Sync Manager for Multi-Agent Network.
Public exports are metadata-only: exact target addresses and credential material
must never be written to Git-synced artifacts.
"""

import os
import sys
import gzip
import shutil
import sqlite3
import datetime
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "isp_cidr.db")
SCANS_DIR = os.path.join(BASE_DIR, "data", "scans")


def get_now_str():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")


def _public_target_id(value):
    from report_sanitize import target_id
    salt = os.environ.get("SCAN_PUBLIC_ID_SALT", "")
    if not salt:
        raise RuntimeError("SCAN_PUBLIC_ID_SALT is required for public exports")
    return target_id(str(value), salt)


def export_and_compress_scans(agent_id="aios"):
    os.makedirs(SCANS_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE):
        return None
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scan_results'")
    if not cur.fetchone():
        conn.close()
        return None
    cur.execute("""
        SELECT ip, port, http_status, server_header, title, asn, isp_name,
               country_code, country_name_ru, response_time_ms, scanned_at
        FROM scan_results WHERE has_banner = 1 ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    chunk_name = f"scan_{agent_id}_{get_now_str()}.csv.gz"
    chunk_path = os.path.join(SCANS_DIR, chunk_name)
    print(f"📦 Сжатие {len(rows):,} найденных баннеров в {chunk_name}...")
    with gzip.open(chunk_path, "wt", encoding="utf-8") as f:
        f.write("Target_ID,Port,HTTP_Status,Server_Header,Title,ASN,ISP_Name,Country_Code,Country_Name,Latency_MS,Scanned_At\n")
        for r in rows:
            srv = (r[3] or "").replace('"', '""')
            title = (r[4] or "").replace('"', '""')
            isp = (r[6] or "").replace('"', '""')
            f.write(f'{_public_target_id(r[0])},{r[1]},{r[2] or ""},"{srv}","{title}",{r[5]},"{isp}",{r[7]},{r[8]},{r[9]},{r[10]}\n')
    size_kb = os.path.getsize(chunk_path) / 1024
    print(f"✅ Чанк сохранен: {chunk_path} ({size_kb:.1f} KB)")
    return chunk_path


def check_db_integrity():
    """Проверка целостности БД + checkpoint WAL перед синком."""
    if not os.path.exists(DB_FILE):
        return False
    try:
        conn = sqlite3.connect(DB_FILE, timeout=60)
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        res = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        ok = res and res[0] == "ok"
        print(f"🧪 Целостность БД: {'OK' if ok else 'ПОВРЕЖДЕНА: ' + str(res)}")
        return ok
    except Exception as e:
        print(f"⚠️ Ошибка проверки БД: {e}")
        return False


def compress_main_db():
    if not os.path.exists(DB_FILE):
        return
    check_db_integrity()
    conn = sqlite3.connect(DB_FILE, timeout=60)
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA page_size = 4096;")
    conn.execute("VACUUM;")
    conn.close()
    raw_mb = os.path.getsize(DB_FILE) / (1024 * 1024)
    print(f"📊 Текущий размер isp_cidr.db: {raw_mb:.2f} МБ")
    gz_path = DB_FILE + ".gz"
    print(f"🗜 Архивирование базы в {gz_path}...")
    with open(DB_FILE, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)
    gz_mb = os.path.getsize(gz_path) / (1024 * 1024)
    print(f"✅ База сжата: {gz_mb:.2f} МБ (сжатие в {raw_mb/gz_mb:.1f} раз!)")


def export_routers(agent_id="aios"):
    """Export router inventory without exact target addresses."""
    routers_dir = os.path.join(BASE_DIR, "data", "routers")
    os.makedirs(routers_dir, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT ip, port, http_status, vendor, model, device_type, confidence, matched_on,
                   server_header, title, asn, isp_name, country_code, country_name_ru, detected_at
            FROM scan_routers ORDER BY detected_at DESC
        """)
    except sqlite3.OperationalError:
        conn.close()
        return None
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print("ℹ️ Таблица scan_routers пуста — экспорт пропущен.")
        return None
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    chunk_path = os.path.join(routers_dir, f"scan_routers_{agent_id}_{ts}.csv.gz")
    with gzip.open(chunk_path, "wt", encoding="utf-8") as f:
        f.write("Target_ID,Port,HTTP_Status,Vendor,Model,Device_Type,Confidence,Matched_On,Server_Header,Title,ASN,ISP_Name,Country_Code,Country_Name,Detected_At\n")
        for r in rows:
            def q(v):
                v = "" if v is None else str(v)
                return '"' + v.replace('"', '""') + '"' if any(c in v for c in '",\n\r') else v
            values = (_public_target_id(r[0]),) + r[1:]
            f.write(",".join(q(x) for x in values) + "\n")
    print(f"✅ Безопасный экспорт роутеров: {chunk_path} ({os.path.getsize(chunk_path)/1024:.1f} KB, {len(rows):,} записей)")
    return chunk_path


def export_credentials(agent_id="aios"):
    """Export only aggregate authentication metadata, never credential material."""
    creds_dir = os.path.join(BASE_DIR, "data", "creds")
    os.makedirs(creds_dir, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT vendor, auth_method, COUNT(*)
            FROM router_credentials
            GROUP BY vendor, auth_method ORDER BY vendor, auth_method
        """)
    except sqlite3.OperationalError:
        conn.close()
        return None
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print("ℹ️ Таблица router_credentials пуста — экспорт пропущен.")
        return None
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    chunk_path = os.path.join(creds_dir, f"router_credentials_summary_{agent_id}_{ts}.csv.gz")
    with gzip.open(chunk_path, "wt", encoding="utf-8") as f:
        f.write("Vendor,Auth_Method,Count\n")
        for vendor, auth_method, count in rows:
            def q(v):
                v = "" if v is None else str(v)
                return '"' + v.replace('"', '""') + '"' if any(c in v for c in '",\n\r') else v
            f.write(",".join(q(x) for x in (vendor, auth_method, count)) + "\n")
    print(f"✅ Безопасный агрегированный экспорт auth-метаданных: {chunk_path} ({os.path.getsize(chunk_path)/1024:.1f} KB, {sum(r[2] for r in rows):,} записей)")
    return chunk_path


def sync_to_github(commit_msg=None):
    os.chdir(BASE_DIR)
    if not commit_msg:
        commit_msg = f"chore(sync): automated data sync & scan chunks at {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    print("🚀 Отправка изменений в Git...")
    subprocess.run(["git", "add", "data/", "STATUS.md", "agent_state.json", "*.py", "*.sh", "*.md"], check=False)
    db_size_mb = os.path.getsize(DB_FILE) / (1024 * 1024) if os.path.exists(DB_FILE) else 0
    if db_size_mb < 95.0:
        subprocess.run(["git", "add", "isp_cidr.db"], check=False)
    else:
        subprocess.run(["git", "add", "isp_cidr.db.gz"], check=False)
    subprocess.run(["git", "commit", "-m", commit_msg], check=False)
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False, env=env, capture_output=True, text=True)
    res = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, env=env)
    if res.returncode == 0:
        print("🎉 Успешно синхронизировано с GitHub!")
    else:
        print(f"⚠️ Git push output: {res.stderr or res.stdout}")


def main():
    agent = sys.argv[1] if len(sys.argv) > 1 else "aios-server"
    print("=== 🔄 Запуск Storage Scaling Manager ===")
    export_and_compress_scans(agent)
    export_routers(agent)
    export_credentials(agent)
    compress_main_db()
    sync_to_github()


if __name__ == "__main__":
    main()
