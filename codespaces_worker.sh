#!/bin/bash
# ============================================================================
# Worker для GitHub Codespaces.
# Запускает один явно авторизованный шард и фиксирует его completion state.
# Требуются SCAN_JOB_ID, SCAN_AUTHORIZATION_REF и SCAN_SCOPE_REF.
# ============================================================================
set -euo pipefail
cd /workspaces/* 2>/dev/null || cd /root/scan 2>/dev/null || cd "$(dirname "$0")/.."

SHARD=${SHARD:-${1:-0}}
TOTAL=${TOTAL:-${2:-4}}
BATCH=${BATCH:-${3:-100000}}
PORTS=${PORTS:-80,8080,8443}
: "${SCAN_JOB_ID:?SCAN_JOB_ID is required}"
: "${SCAN_AUTHORIZATION_REF:?SCAN_AUTHORIZATION_REF is required}"
: "${SCAN_SCOPE_REF:?SCAN_SCOPE_REF is required}"
SCAN_CONCURRENCY=${SCAN_CONCURRENCY:-100}
SCAN_MAX_CONCURRENCY=${SCAN_MAX_CONCURRENCY:-500}
SCAN_TIMEOUT=${SCAN_TIMEOUT:-2.0}
case "$SCAN_CONCURRENCY" in ''|*[!0-9]*) echo "SCAN_CONCURRENCY must be numeric" >&2; exit 2;; esac
[ "$SCAN_CONCURRENCY" -gt 0 ] && [ "$SCAN_CONCURRENCY" -le "$SCAN_MAX_CONCURRENCY" ] || { echo "SCAN_CONCURRENCY out of bounds" >&2; exit 2; }

echo "=== Codespaces Worker: шард $SHARD/$TOTAL, batch=$BATCH, порты=$PORTS ==="

git pull --rebase origin main >/dev/null 2>&1
pip install --quiet paramiko playwright==1.62.0 pytest 2>/dev/null || true

if [ ! -f isp_cidr.db ] && [ -f isp_cidr.db.gz ]; then
  gunzip -kf isp_cidr.db.gz
fi

ulimit -n 65535 2>/dev/null || true
CMD="python3 port_scanner.py run --batch $BATCH --shard $SHARD --shard-total $TOTAL --concurrency $SCAN_CONCURRENCY --timeout $SCAN_TIMEOUT --ports '$PORTS'"
python3 -c 'import sys; from shard_executor import execute_shard; raise SystemExit(execute_shard(sys.argv[1], sys.argv[2]))' \
  "shard:$SHARD" "$CMD"

echo "=== Worker завершён; shard:$SHARD зафиксирован как выполненный ==="
