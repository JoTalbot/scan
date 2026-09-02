#!/usr/bin/env python3
"""Storage Scaling & Auto-Sync Manager.

Credential exports are metadata-only. Never export credential material.
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

def export_and_compress_scans(agent_id="aios"):
    os.makedirs(SCANS_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE): return None
    conn = sqlite3.connect(DB_FILE); cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scan_results'")
    if not cur.fetchone(): conn.close(); return None
    cur.execute("SELECT ip, port, http_status, server_header, title, asn, isp_name, country_code, country_name_ru, response_time_ms, scanned_at FROM scan_results WHERE has_banner = 1 ORDER BY id DESC")
    rows = cur.fetchall(); conn.close()
    if not rows: return None
    chunk_path = os.path.join(SCANS_DIR, f"scan_{agent_id}_{get_now_str()}.csv.gz")
    with gzip.open(chunk_path, "wt", encoding="utf-8") as f:
        f.write("IP,Port,HTTP_Status,Server_Header,Title,ASN,ISP_Name,Country_Code,Country_Name,Latency_MS,Scanned_At\n")
        for r in rows:
            q=lambda v: '"'+str(v or '').replace('"','""')+'"'
            f.write(f'{r[0]},{r[1]},{r[2] or ""},{q(r[3])},{q(r[4])},{r[5]},"{str(r[6] or "").replace(chr(34), chr(34)*2)}",{r[7]},{r[8]},{r[9]},{r[10]}\n')
    return chunk_path

def check_db_integrity():
    if not os.path.exists(DB_FILE): return False
    try:
        conn=sqlite3.connect(DB_FILE, timeout=60); conn.execute("PRAGMA busy_timeout = 30000;"); conn.execute("PRAGMA wal_checkpoint(TRUNCATE);"); res=conn.execute("PRAGMA integrity_check").fetchone(); conn.close()
        return bool(res and res[0] == "ok")
    except Exception as e:
        print(f"⚠️ Ошибка проверки БД: {e}"); return False

def compress_main_db():
    if not os.path.exists(DB_FILE): return
    check_db_integrity(); conn=sqlite3.connect(DB_FILE, timeout=60); conn.execute("PRAGMA busy_timeout = 30000;"); conn.execute("VACUUM;"); conn.close()
    with open(DB_FILE,"rb") as f_in, gzip.open(DB_FILE+".gz","wb",compresslevel=6) as f_out: shutil.copyfileobj(f_in,f_out)

def export_routers(agent_id="aios"):
    routers_dir=os.path.join(BASE_DIR,"data","routers"); os.makedirs(routers_dir,exist_ok=True)
    conn=sqlite3.connect(DB_FILE); cur=conn.cursor()
    try: cur.execute("SELECT ip, port, http_status, vendor, model, device_type, confidence, matched_on, server_header, title, asn, isp_name, country_code, country_name_ru, detected_at FROM scan_routers ORDER BY detected_at DESC")
    except sqlite3.OperationalError: conn.close(); return None
    rows=cur.fetchall(); conn.close()
    if not rows: return None
    path=os.path.join(routers_dir,f"scan_routers_{agent_id}_{get_now_str()}.csv.gz")
    with gzip.open(path,"wt",encoding="utf-8") as f:
        f.write("IP,Port,HTTP_Status,Vendor,Model,Device_Type,Confidence,Matched_On,Server_Header,Title,ASN,ISP_Name,Country_Code,Country_Name,Detected_At\n")
        for r in rows:
            def q(v):
                v="" if v is None else str(v); return '"'+v.replace('"','""')+'"' if any(c in v for c in '",\n\r') else v
            f.write(",".join(q(x) for x in r)+"\n")
    return path

def export_credentials(agent_id="aios"):
    """Write aggregate authentication metadata only, never target or credential values."""
    creds_dir=os.path.join(BASE_DIR,"data","creds"); os.makedirs(creds_dir,exist_ok=True)
    conn=sqlite3.connect(DB_FILE); cur=conn.cursor()
    try: cur.execute("SELECT vendor, auth_method, COUNT(*) FROM router_credentials GROUP BY vendor, auth_method ORDER BY vendor, auth_method")
    except sqlite3.OperationalError: conn.close(); return None
    rows=cur.fetchall(); conn.close()
    if not rows: return None
    path=os.path.join(creds_dir,f"router_credentials_summary_{agent_id}_{get_now_str()}.csv.gz")
    with gzip.open(path,"wt",encoding="utf-8") as f:
        f.write("Vendor,Auth_Method,Count\n")
        for vendor, method, count in rows:
            q=lambda v: '"'+str(v or '').replace('"','""')+'"' if any(c in str(v or '') for c in '",\n\r') else str(v or '')
            f.write(",".join(q(x) for x in (vendor,method,count))+"\n")
    return path

def sync_to_github(commit_msg=None):
    os.chdir(BASE_DIR)
    if not commit_msg: commit_msg=f"chore(sync): automated data sync at {get_now_str()}"
    subprocess.run(["git","add","data/","STATUS.md","agent_state.json","*.py","*.sh","*.md"],check=False)
    if os.path.exists(DB_FILE): subprocess.run(["git","add","isp_cidr.db" if os.path.getsize(DB_FILE)<95*1024*1024 else "isp_cidr.db.gz"],check=False)
    subprocess.run(["git","commit","-m",commit_msg],check=False)
    env=dict(os.environ,GIT_TERMINAL_PROMPT="0")
    subprocess.run(["git","pull","--rebase","origin","main"],check=False,env=env,capture_output=True,text=True)
    res=subprocess.run(["git","push","origin","main"],capture_output=True,text=True,env=env)
    print("🎉 Успешно синхронизировано с GitHub!" if res.returncode==0 else f"⚠️ Git push output: {res.stderr or res.stdout}")

def main():
    agent=sys.argv[1] if len(sys.argv)>1 else "aios-server"
    export_and_compress_scans(agent); export_routers(agent); export_credentials(agent); compress_main_db(); sync_to_github()

if __name__ == "__main__": main()
