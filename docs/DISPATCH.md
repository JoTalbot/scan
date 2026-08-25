# 📦 Dispatcher — раздача задач по машинам

## Что это
`dispatch.py` генерирует шарды задач и раздаёт их доступным исполнителям
(машинам). Сейчас доступен только `local`; остальные подключаются по шагам ниже.

## Исполнители и как их подключить

### 1. local (всегда доступен)
N параллельных процессов на текущем сервере. Ничего не нужно.

### 2. SSH-машины (Oracle ARM, VPS) ⭐ рекомендуемо
```bash
# 1. На новой машине: установить репо и зависимости
ssh root@<новая-машина> "apt-get update && apt-get install -y git python3 python3-pip sqlite3 && \
  git clone https://github.com/JoTalbot/scan.git /root/scan && cd /root/scan && \
  pip3 install paramiko playwright pytest"

# 2. С этого сервера скопировать SSH-ключ (нужен для бесключевого входа)
ssh-copy-id root@<новая-машина>

# 3. Раздать с учётом новой машины
MACHINES="<новая-машина>" python3 dispatch.py scan --batch 100000 --shards 4 --parallel
# или принудительно:
python3 dispatch.py scan --batch 100000 --shards 4 --force-ssh "<m1>,<m2>"
```
Проверка: `python3 dispatch.py --workers` покажет `ssh: [<m1>, <m2>]`.

### 3. GitHub Codespaces (120 core-ч/мес)
```bash
# 1. Установить gh CLI и авторизоваться (на сервере)
apt-get install -y gh   # или по докам https://cli.github.com
gh auth login           # с токеном или браузером

# 2. Проверка
python3 dispatch.py --workers   # появится "codespaces (gh CLI авторизован)"

# 3. Раздача (создаст кодаспейсы с .devcontainer из репо)
python3 dispatch.py scan --batch 100000 --shards 6 --parallel
```
Квоты: 120 core-ч/мес (≈60 ч на 2-core), 15 ГБ storage. Удалять кодаспейсы после:
`gh codespace list && gh codespace delete -c <name>`.

### 4. E2B песочницы ($100 кредитов)
```bash
# 1. Получить ключ на e2b.dev (Sign up → API keys)
export E2B_API_KEY=e2b_...

# 2. Проверка
python3 dispatch.py --workers   # появится "e2b (ключ есть)"

# 3. Раздача тяжёлого аудита в песочницах
python3 dispatch.py audit_browser --shards 3 --parallel
```
Примечание: e2b_audit.py клонирует репо в песочницу и скачивает результаты в `downloads/`.

## Примеры
```bash
# Полный скан 100k на 4 машинах
python3 dispatch.py scan --batch 100000 --shards 4 --parallel

# Аудит raw на 2 исполнителях
python3 dispatch.py audit_raw --shards 2

# Показать исполнителей
python3 dispatch.py --workers
```

## Как это работает
1. `dispatch.py` определяет доступных исполнителей (ssh → codespaces → e2b → local)
2. Для `scan`: шарды распределяются по исполнителям по кругу
3. Каждый шард: `git pull` + `port_scanner.py run --shard i/total` + лог в `logs/dispatch/`
4. Мониторинг завершения (параллельно или последовательно)
5. По завершении: `sync_manager.py` — пуш результатов на GitHub

## Ограничения и советы
- Разные машины используют **общую БД через git** (WAL + busy_timeout 30с) — конфликтов нет
- Перед запуском на машинах-исполнителях должен быть клон репо (см. шаг 2)
- Codespaces: разовые шарды, не постоянные сервисы (ToS)
- E2B: ключ обязателен; сессии до 1 ч на Hobby
