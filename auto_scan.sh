#!/bin/bash
set -euo pipefail

BATCH_SIZE="${BATCH_SIZE:-${1:-10000}}"
CONCURRENCY="${CONCURRENCY:-${2:-100}}"
MAX_CONCURRENCY="${MAX_CONCURRENCY:-500}"
TIMEOUT="${SCAN_TIMEOUT:-2.0}"
AGENT_ID="${SCAN_AGENT_ID:-aios-agent-01}"
MACHINE_ID="${SCAN_MACHINE_ID:-aios-server}"
SCAN_ROOT="${SCAN_ROOT:-$(cd "$(dirname "$0")" && pwd)}"
AUTH_REF="${SCAN_AUTHORIZATION_REF:-}"

if [[ -z "$AUTH_REF" ]]; then
  echo "ERROR: SCAN_AUTHORIZATION_REF is required. Refusing active scan without explicit authorization." >&2
  exit 2
fi

if ! [[ "$CONCURRENCY" =~ ^[0-9]+$ ]] || (( CONCURRENCY < 1 || CONCURRENCY > MAX_CONCURRENCY )); then
  echo "ERROR: concurrency must be between 1 and $MAX_CONCURRENCY" >&2
  exit 2
fi

cd "$SCAN_ROOT"

echo "=========================================="
echo "Authorized scan: batch=$BATCH_SIZE concurrency=$CONCURRENCY timeout=$TIMEOUT"
echo "Authorization reference: $AUTH_REF"
echo "=========================================="

python3 agent_sync.py lock --agent "$AGENT_ID" --task "Port 80 Scan" --step "Сканирование $BATCH_SIZE IP" --machine "$MACHINE_ID"

ulimit -n 65535 2>/dev/null || true
python3 port_scanner.py run --batch "$BATCH_SIZE" --concurrency "$CONCURRENCY" --timeout "$TIMEOUT"

python3 agent_sync.py complete --agent "$AGENT_ID" --task "Port 80 Scan"
python3 sync_manager.py "$AGENT_ID"

echo "=========================================="
echo "Scan completed."
echo "=========================================="
