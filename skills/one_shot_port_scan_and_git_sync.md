# 🔍 Одноразовое сканирование порта 80 + безопасная синхронизация с GitHub

## Контекст применения
Запуск одноразовой партии сканирования N IP (порт 80) с сохранением результатов в SQLite, экспортом чанка баннеров и пушем в GitHub, не превышая лимит размера файла (100 МБ).

## Входные данные и предварительные требования
- Сервер с репозиторием `/root/scan` (Python 3.10+, без внешних зависимостей).
- SQLite БД `isp_cidr.db` с таблицами `ip_ranges` / `v_ip_ranges` и `scan_results`.
- GitHub remote + credential helper (`git config credential.helper store`), токен в `.env` (НЕ в remote URL!).

## Пошаговый алгоритм
1. **Синхронизация:** `git pull --rebase` (сначала закоммитить/stash незакоммиченные изменения).
2. **Lock задачи:** `python3 agent_sync.py lock --agent "<AGENT>" --task "Port 80 Scan (one-shot N)" --step "..." --machine "<HOST>"`.
3. **Запуск скана** (фоновый, переживает SSH): `setsid nohup python3 port_scanner.py run --batch 10000 --concurrency 500 --timeout 2.0 > logs/scan_10k.log 2>&1 < /dev/null &`.
4. **Мониторинг:** `cat logs/scan_10k.log` — прогресс печатается каждые 250 IP; скорость ~260 IP/сек.
5. **Complete:** `python3 agent_sync.py complete --agent "<AGENT>" --task "..."`.
6. **Обновить ченджлог** в `STATUS.md` (метрики: время, открытые порты, баннеры).
7. **Синхронизация:** `python3 sync_manager.py "<AGENT>"` — экспорт `data/scans/*.csv.gz`, VACUUM + gzip БД, git add/commit/push.

## Критично: лимит GitHub 100 МБ
- GitHub отклоняет push файлов > 100 МБ (`GH001: Large files detected`).
- Логика `sync_manager.py`: БД < 95 МБ → трекается `isp_cidr.db`; БД > 95 МБ → трекается `isp_cidr.db.gz` (30 МБ), raw `.db` остаётся untracked локально.
- Если raw `.db` уже добавлен в индекс: `git reset --soft HEAD~1 && git rm --cached isp_cidr.db`, затем `git add isp_cidr.db.gz` — и push пройдёт.

## Безопасность секретов
- GitHub-токен НЕ должен быть в remote URL (`https://TOKEN@github.com/...` светится в `.git/config`).
- Перенос: извлечь токен из remote URL через sed, записать в `.env` (в `.gitignore`), `git remote set-url origin https://github.com/<user>/<repo>.git`, credential helper `store` хранит токен в `~/.git-credentials` (chmod 600).

## Типичные ошибки
- `error: cannot pull with rebase: You have unstaged changes` → сначала commit/stash.
- Push rejected: `pre-receive hook declined` → проверьте размер файла, переключитесь на `.gz`.
- Фоновый скан умирает с SSH → использовать `setsid nohup ... < /dev/null &`.
- Статус-таблица STATUS.md задваивается → секцию Active Tasks перегенерирует `agent_sync.py` (от `## 🟢` до `---`), не редактировать её вручную параллельно.

## Критерии верификации
- `git log --oneline` содержит коммит `chore(sync): automated data sync...`.
- `git status` чистый; `.env` не в коммитах.
- В БД: `SELECT COUNT(*) FROM scan_results` вырос ровно на N; чанк `data/scans/scan_*.csv.gz` создан.
