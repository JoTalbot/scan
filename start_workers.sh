#!/bin/bash
# ============================================================================
# Мультимашинное сканирование: запуск N шардов с durable/idempotent state.
# Требуются явные SCAN_JOB_ID, SCAN_AUTHORIZATION_REF и SCAN_SCOPE_REF.
# ============================================================================
set -euo pipefail
cd /root/scan

WORKERS=${1:-4}
BATCH=${2:-100000}
PORTS=${PORTS:-80,8080,8443}
MACHINES="${MACHINES:-}"
: "${SCAN_JOB_ID:?SCAN_JOB_ID is required}"
: "${SCAN_AUTHORIZATION_REF:?SCAN_AUTHORIZATION_REF is required}"
: "${SCAN_SCOPE_REF:?SCAN_SCOPE_REF is required}"

case "$WORKERS" in ''|*[!0-9]*) echo "WORKERS must be numeric" >&2; exit 2;; esac
[ "$WORKERS" -gt 0 ] || { echo "WORKERS must be > 0" >&2; exit 2; }

# Базовые параметры выполнения берутся из окружения и остаются ограниченными.
SCAN_CONCURRENCY=${SCAN_CONCURRENCY:-100}
SCAN_MAX_CONCURRENCY=${SCAN_MAX_CONCURRENCY:-500}
SCAN_TIMEOUT=${SCAN_TIMEOUT:-2.0}
case "$SCAN_CONCURRENCY" in ''|*[!0-9]*) echo "SCAN_CONCURRENCY must be numeric" >&2; exit 2;; esac
[ "$SCAN_CONCURRENCY" -gt 0 ] && [ "$SCAN_CONCURRENCY" -le "$SCAN_MAX_CONCURRENCY" ] || {
  echo "SCAN_CONCURRENCY must be within 1..$SCAN_MAX_CONCURRENCY" >&2; exit 2;
}

echo "=== Мультимашинный скан: $WORKERS шардов x $BATCH IP (порты: $PORTS) ==="

# 1. синхронизация кода на удалённых машинах
if [ -n "$MACHINES" ]; then
  for M in $(echo "$MACHINES" | tr ',' ' '); do
    ssh -o StrictHostKeyChecking=no root@"$M" "cd /root/scan && git pull --rebase origin main" >/dev/null 2>&1
  done
fi
git pull --rebase origin main >/dev/null 2>&1

run_shard() {
  local shard="$1"
  local cmd
  cmd="python3 port_scanner.py run --batch $BATCH --shard $shard --shard-total $WORKERS --concurrency $SCAN_CONCURRENCY --timeout $SCAN_TIMEOUT --ports '$PORTS'"
  python3 -c 'import sys; from shard_executor import execute_shard; raise SystemExit(execute_shard(sys.argv[1], sys.argv[2]))' \
    "shard:$shard" "$cmd"
}

# 2. запуск шардов. Уже завершённые шарды shard_executor пропустит.
for i in $(seq 0 $((WORKERS - 1))); do
  if [ -z "$MACHINES" ]; then
    (ulimit -n 65535 && run_shard "$i" > "logs/shard_${i}.log" 2>&1) &
    echo "  шард $((i+1))/$WORKERS запущен локально (logs/shard_${i}.log)"
  else
    M=$(echo "$MACHINES" | cut -d, -f$((i + 1)))
    ssh -o StrictHostKeyChecking=no root@"$M" "cd /root/scan && export SCAN_JOB_ID='$SCAN_JOB_ID' SCAN_AUTHORIZATION_REF='$SCAN_AUTHORIZATION_REF' SCAN_SCOPE_REF='$SCAN_SCOPE_REF' SCAN_CONCURRENCY='$SCAN_CONCURRENCY' SCAN_MAX_CONCURRENCY='$SCAN_MAX_CONCURRENCY' SCAN_TIMEOUT='$SCAN_TIMEOUT' PORTS='$PORTS'; ulimit -n 65535; python3 -c 'import sys; from shard_executor import execute_shard; raise SystemExit(execute_shard(sys.argv[1], sys.argv[2]))' 'shard:$i' \"python3 port_scanner.py run --batch $BATCH --shard $i --shard-total $WORKERS --concurrency $SCAN_CONCURRENCY --timeout $SCAN_TIMEOUT --ports '$PORTS'\" > "logs/shard_${i}.log" 2>&1" &
    echo "  шард $((i+1))/$WORKERS запущен на $M"
  fi
done

if [ -z "$MACHINES" ]; then
  echo "Ожидание завершения $WORKERS шардов..."
  wait
  echo "Все шарды завершены."
  for i in $(seq 0 $((WORKERS - 1))); do
    grep -h "✨" "logs/shard_${i}.log" 2>/dev/null | tail -1 || true
  done
fi

echo "=== Готово. Завершённые шарды зафиксированы в durable job state. ==="
