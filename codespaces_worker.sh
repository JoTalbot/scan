#!/bin/bash
# ============================================================================
# Worker для GitHub Codespaces (№2 плана)
# Запускает шард сканирования из Codespace и пушит результаты.
#
# Использование (в терминале Codespace):
#   ./codespaces_worker.sh 0 4 100000     # шард 0 из 4, batch 100k
#   SHARD=2 TOTAL=4 BATCH=100000 ./codespaces_worker.sh
#
# Квоты Codespaces (личный аккаунт): 120 core-часов/мес (~60 ч на 2-core),
# 15 ГБ-мес хранилища. 4 шарда x 100k займут ~3-4 мин.
# ============================================================================
set -e
cd /workspaces/* 2>/dev/null || cd /root/scan 2>/dev/null || cd "$(dirname "$0")/.."

SHARD=${SHARD:-${1:-0}}
TOTAL=${TOTAL:-${2:-4}}
BATCH=${BATCH:-${3:-100000}}
PORTS=${PORTS:-80,8080,8443}

echo "=== Codespaces Worker: шард $SHARD/$TOTAL, batch=$BATCH, порты=$PORTS ==="

# 1. Синхронизация репо
git pull --rebase origin main 2>&1 | tail -1 || true

# 2. Зависимости (если не установлены postCreateCommand'ом)
pip install --quiet paramiko playwright==1.62.0 pytest 2>/dev/null || true

# 3. БД (распаковать из LFS-архива, если нет)
if [ ! -f isp_cidr.db ]; then
  echo "Распаковываю БД из isp_cidr.db.gz..."
  gunzip -kf isp_cidr.db.gz || true
fi

# 4. Скан шарда
ulimit -n 65535 2>/dev/null || true
python3 port_scanner.py run --batch "$BATCH" --shard "$SHARD" --shard-total "$TOTAL" \
  --concurrency 1000 --timeout 1.0 --ports "$PORTS"

# 5. Пуш результатов (только этот шард коммитит — остальные ждут)
if [ "$SHARD" = "0" ]; then
  echo "Шард 0: синхронизирую и пушу результаты всех шардов..."
  sleep 30   # даём остальным шардам закончить
  python3 sync_manager.py "codespaces-worker-$SHARD"
fi

echo "=== Worker завершён ==="
