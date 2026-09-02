#!/bin/bash
# Authorized pipeline: scan -> detect -> audit -> enrichment -> sync
set -euo pipefail

SCAN_ROOT="${SCAN_ROOT:-$(cd "$(dirname "$0")" && pwd)}"
cd "$SCAN_ROOT"

BATCH="${BATCH_SIZE:-${1:-10000}}"
CONCURRENCY="${SCAN_CONCURRENCY:-100}"
MAX_CONCURRENCY="${SCAN_MAX_CONCURRENCY:-500}"
TIMEOUT="${SCAN_TIMEOUT:-2.0}"
AGENT="${SCAN_AGENT_ID:-Agent-Arena-01}"
MACHINE="${SCAN_MACHINE_ID:-aios-server}"
AUTH_REF="${SCAN_AUTHORIZATION_REF:-}"
SCAN_MODE="${SCAN_MODE:-local}"
PORTS="${PORTS:-80,8080,8443}"

if [[ -z "$AUTH_REF" ]]; then
  echo "ERROR: SCAN_AUTHORIZATION_REF is required; refusing active pipeline." >&2
  exit 2
fi
if ! [[ "$CONCURRENCY" =~ ^[0-9]+$ ]] || (( CONCURRENCY < 1 || CONCURRENCY > MAX_CONCURRENCY )); then
  echo "ERROR: invalid concurrency=$CONCURRENCY (allowed 1..$MAX_CONCURRENCY)" >&2
  exit 2
fi

TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG="logs/pipeline_$(date -u +%Y%m%d_%H%M%S).log"
mkdir -p logs
log() { echo "[$(date -u +%H:%M:%S)] $1" | tee -a "$LOG"; }

log "=== PIPELINE START ($TS, batch=$BATCH, mode=$SCAN_MODE) ==="
log "Authorization reference supplied: yes"

FREE_GB=$(df -BG / | awk 'NR==2 {gsub("G","",$4); print $4}')
log "Free disk: ${FREE_GB}G"
if (( FREE_GB < 3 )); then
  log "Low disk space; cleaning old generated artifacts."
  find data/scans -name "*.csv.gz" -mtime +3 -delete 2>/dev/null || true
  find logs -name "*.log*" -mtime +7 -delete 2>/dev/null || true
  find "$SCAN_ROOT" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
fi

BK_DIR="${SCAN_ROOT}/backups"
mkdir -p "$BK_DIR"
BK_FILE="$BK_DIR/isp_cidr_$(date -u +%Y%m%d).db.gz"
if [[ ! -f "$BK_FILE" && -f isp_cidr.db ]]; then
  log "Creating database backup."
  gzip -c isp_cidr.db > "$BK_FILE"
  find "$BK_DIR" -name "*.db.gz" -mtime +7 -delete 2>/dev/null || true
fi

log "Synchronizing source."
git pull --rebase origin main >> "$LOG" 2>&1

python3 agent_sync.py lock --agent "$AGENT" --task "Auto pipeline scan" \
  --step "Scanning $BATCH IP" --machine "$MACHINE" >> "$LOG" 2>&1

if [[ "$SCAN_MODE" == "dispatch" ]]; then
  SHARDS="${SHARDS:-3}"
  log "Dispatch scan: batch=$BATCH shards=$SHARDS ports=$PORTS"
  timeout 3600 python3 -u dispatch.py scan --batch "$BATCH" --shards "$SHARDS" --ports "$PORTS" --parallel >> "$LOG" 2>&1
else
  log "Local scan: batch=$BATCH concurrency=$CONCURRENCY timeout=$TIMEOUT ports=$PORTS"
  ulimit -n 65535 2>/dev/null || true
  python3 port_scanner.py run --batch "$BATCH" --concurrency "$CONCURRENCY" --timeout "$TIMEOUT" --ports "$PORTS" >> "$LOG" 2>&1
fi

NEW_RAW=$(python3 - <<'PY'
import sqlite3
with sqlite3.connect('isp_cidr.db') as conn:
    print(conn.execute('SELECT COUNT(*) FROM scan_routers WHERE auth_checked=0').fetchone()[0])
PY
)
NEW_BR=$(python3 - <<'PY'
import sqlite3
with sqlite3.connect('isp_cidr.db') as conn:
    print(conn.execute('SELECT COUNT(*) FROM scan_routers WHERE browser_checked=0 AND auth_result="no-verifiable-channel"').fetchone()[0])
PY
)
log "New routers: raw=$NEW_RAW browser=$NEW_BR"

if (( NEW_RAW > 0 )); then
  log "Running fast raw audit for $NEW_RAW devices."
  python3 router_auth_check.py --fast --concurrency 30 --timeout 4 >> "$LOG" 2>&1
fi

AUDIT_MODE="${AUDIT_MODE:-manual}"
if [[ "$AUDIT_MODE" == "auto" && "$NEW_BR" -gt 0 ]]; then
  log "Browser audit via dispatch."
  timeout 2400 python3 dispatch.py audit_browser --shards 2 >> "$LOG" 2>&1
  timeout 1200 python3 dispatch.py csb_probe --batch 20 >> "$LOG" 2>&1
  timeout 1200 python3 dispatch.py e2b_probe --batch 20 >> "$LOG" 2>&1
elif [[ "$NEW_BR" -gt 0 ]]; then
  log "Browser audit in manual mode."
  .venv/bin/python -u router_auth_browser.py --only-no-channel --pairs 8 --concurrency 4 --timeout 7 --wait 2.5 >> "$LOG" 2>&1
fi

if [[ "${INTERNETDB:-0}" == "1" ]]; then
  log "InternetDB enrichment."
  timeout 600 python3 internetdb_enrich.py --delay 0.2 >> "$LOG" 2>&1
fi

FOUND=$(python3 - <<'PY'
import sqlite3
with sqlite3.connect('isp_cidr.db') as conn:
    print(conn.execute('SELECT COUNT(*) FROM router_credentials').fetchone()[0])
PY
)
log "Verified credential findings: $FOUND (credential values intentionally omitted from logs)."

# Never print or send discovered credentials. Downstream notifications should
# carry only a count and a redacted finding identifier.
if (( FOUND > 0 )) && [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  MSG="RouterScan: verified credential finding count=$FOUND; details are redacted."
  curl -fsS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" -d text="$MSG" > /dev/null
fi

python3 agent_sync.py complete --agent "$AGENT" --task "Auto pipeline scan" >> "$LOG" 2>&1
python3 sync_manager.py "$AGENT" >> "$LOG" 2>&1
log "=== PIPELINE DONE ==="
