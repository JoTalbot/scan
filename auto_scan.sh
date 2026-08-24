#!/bin/bash
set -e

BATCH_SIZE=${1:-100000}
CONCURRENCY=${2:-1000}
AGENT_ID="aios-agent-01"

cd /root/scan

echo "=========================================="
echo "🚀 Запуск сканирования $BATCH_SIZE IP в $CONCURRENCY потоков"
echo "=========================================="

# 1. Захват задачи агентом в STATUS.md
python3 agent_sync.py lock --agent "$AGENT_ID" --task "Port 80 Scan" --step "Сканирование $BATCH_SIZE IP" --machine "aios-server" || true

# 2. Сканирование
ulimit -n 65535 2>/dev/null || true
python3 port_scanner.py run --batch "$BATCH_SIZE" --concurrency "$CONCURRENCY" --timeout 1.0

# 3. Завершение задачи в STATUS.md
python3 agent_sync.py complete --agent "$AGENT_ID" --task "Port 80 Scan" || true

# 4. Автоматическое сжатие, выгрузка чанка сканов и пуш на GitHub
python3 sync_manager.py "$AGENT_ID"

echo "=========================================="
echo "✅ Сканирование и сохранение в GitHub завершены!"
echo "=========================================="
