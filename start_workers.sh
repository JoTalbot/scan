#!/bin/bash
# ============================================================================
# Мультимашинное сканирование: запуск N шардов (каждый как отдельная машина)
#
# Локально (N процессов на этом сервере):
#     ./start_workers.sh 4 100000
#
# На разных машинах (список IP/хостов через запятую, SSH-ключ настроен):
#     MACHINES="10.0.0.2,10.0.0.3,10.0.0.4" ./start_workers.sh 4 100000
#
# Каждый шард: свои 1/N целей, общая БД (WAL + busy_timeout 30s),
# результат — один sync_manager push после завершения всех.
# ============================================================================
set -e
cd /root/scan

WORKERS=${1:-4}
BATCH=${2:-100000}
PORTS=${PORTS:-80,8080,8443}
MACHINES="${MACHINES:-}"

echo "=== Мультимашинный скан: $WORKERS шардов x $BATCH IP (порты: $PORTS) ==="

# 1. синхронизация на всех машинах
if [ -n "$MACHINES" ]; then
  for M in $(echo "$MACHINES" | tr ',' ' '); do
    ssh -o StrictHostKeyChecking=no root@"$M" "cd /root/scan && git pull --rebase origin main" >/dev/null 2>&1 || true
  done
fi
git pull --rebase origin main 2>&1 | tail -1 || true

# 2. запуск шардов
PIDS=""
for i in $(seq 0 $((WORKERS - 1))); do
  if [ -z "$MACHINES" ]; then
    # локальный шард
    (ulimit -n 65535 && setsid nohup python3 port_scanner.py run --batch "$BATCH" \
      --shard "$i" --shard-total "$WORKERS" --concurrency 1000 --timeout 1.0 \
      --ports "$PORTS" > "logs/shard_${i}.log" 2>&1 < /dev/null &)
    echo "  шард $((i+1))/$WORKERS запущен локально (logs/shard_${i}.log)"
  else
    # удалённая машина
    M=$(echo "$MACHINES" | cut -d, -f$((i + 1)))
    ssh -o StrictHostKeyChecking=no root@"$M" "cd /root/scan && ulimit -n 65535 && \
      setsid nohup python3 port_scanner.py run --batch $BATCH --shard $i \
      --shard-total $WORKERS --concurrency 1000 --timeout 1.0 --ports $PORTS \
      > logs/shard_${i}.log 2>&1 < /dev/null &" &
    echo "  шард $((i+1))/$WORKERS запущен на $M"
  fi
done

# 3. ожидание завершения всех локальных шардов
if [ -z "$MACHINES" ]; then
  echo "Ожидание завершения $WORKERS шардов..."
  while :; do
    RUNNING=$(pgrep -f "port_scanner.py run" | wc -l)
    [ "$RUNNING" -eq 0 ] && break
    sleep 15
  done
  echo "Все шарды завершены."
  # сводка
  for i in $(seq 0 $((WORKERS - 1))); do
    grep -h "✨" "logs/shard_${i}.log" 2>/dev/null | tail -1
  done
fi

echo "=== Готово. Запустите: python3 sync_manager.py (после завершения всех машин) ==="
