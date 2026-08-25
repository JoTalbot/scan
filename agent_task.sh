#!/bin/bash
# Запуск задачи агента OpenHands (простая, без проблем с кавычками)
cd /root/scan
TASK="$1"
setsid nohup python3 -u dispatch.py dev --task-text "$TASK" > logs/dispatch_dev.log 2>&1 < /dev/null &
echo "PID=$!"
