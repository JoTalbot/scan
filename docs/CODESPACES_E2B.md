# 🚀 GitHub Codespaces + E2B — как использовать (№2, №4)

## Часть A: GitHub Codespaces (120 core-часов/мес бесплатно)

Кодыпейсы дают полноценную облачную VM (devcontainer) с root-доступом и SSH —
«арендный» раннер на ~60 часов реального времени каждый месяц.

### Быстрый старт
1. Откройте репозиторий на GitHub → кнопка **Code → Codespaces → Create codespace on main**.
   Конфиг `.devcontainer/` применится автоматически (Python 3.11 + Playwright + зависимости).
2. В терминале кодаспейса запустите воркер:
   ```bash
   ./codespaces_worker.sh 0 4 100000     # шард 0/4 на 100k IP (~1-2 мин)
   ```
3. Повторите с шардами 1, 2, 3 (можно параллельно в 4 кодаспейсах — лимит 20 одновременных).
4. Шард 0 закоммитит и запушит результаты всех шардов.

### Квоты (личный аккаунт, август 2026)
| Ресурс | Free | Pro ($4/мес) |
| :--- | :--- | :--- |
| Compute | 120 core-часов/мес (= 60 ч на 2-core) | 180 core-часов |
| Storage | 15 ГБ-мес | 20 ГБ-мес |
| Machine | 2-core по умолчанию ($0.18/ч после квоты) | — |

### Полезные команды
```bash
# создание кодаспейса из CLI
gh codespace create --repo JoTalbot/scan

# SSH внутрь
gh codespace ssh

# список и удаление (стоп-кодаспейсы едят storage — удалять!)
gh codespace list
gh codespace delete -c <name>
```

### ⚠️ Важно
- Квоты не бесконечны: 4 кодаспейса по 8 ч = весь лимит. Используйте для **периодических** шардов, не для постоянных сервисов.
- **Удаляйте кодаспейсы** после работы (15 ГБ storage/мес тратятся на остановленные).
- GitHub ToS: кодаспейсы — dev-среды; длительные «серверные» нагрузки (24/7) не приветствуются. Разовые сканы — нормально.

---

## Часть B: E2B Sandboxes (№4 — тяжёлый аудит вне сервера)

E2B — изолированные Firecracker-microVM для ИИ-агентов/скриптов.
Hobby: **$100 разовых кредитов**, до 20 параллельных песочниц, сессии до 1 ч.

### Установка и ключ
```bash
pip install e2b
export E2B_API_KEY=e2b_...   # получить на e2b.dev (Sign up → API keys)
```

### Запуск аудита в песочнице (скрипт e2b_audit.py)
```bash
python3 e2b_audit.py --script router_auth_check.py --args "--fast --vendor MIKROTIK"
python3 e2b_audit.py --script router_auth_browser.py --args "--only-no-channel --pairs 8"
```
Скрипт: создаёт песочницу → клонирует репо → ставит зависимости → запускает
указанный скрипт с аргументами → забирает stdout и файлы (БД/CSV) обратно.

### Зачем это нам
- Playwright-аудит (тяжёлый, по 6-40 сек на устройство) можно вынести в песочницы:
  сервер не грузится, параллельность до 20 песочниц.
- Каждая песочница изолирована — сбой не влияет на основную систему.
- $100 кредитов при $0.000014/с ≈ **~2000 часов** CPU-времени.

### Стоимость (Hobby)
| Ресурс | Цена |
| :--- | :--- |
| CPU | $0.000014/сек |
| RAM | $0.0000045/сек |
| Storage | $0 (в рамках лимитов) |
| Песочницы параллельно | до 20 |
| Сессия | до 1 ч |

### ⚠️ Примечания
- Ключ E2B нужен — без него скрипт покажет инструкцию.
- Из песочницы исходящий интернет есть (нужен для скана), но IP — датацентровый
  E2B; для распределённого скана это плюс (другой источник).
- ToS E2B — платформа «для агентов»; массовые атаки запрещены, исследовательские
  сценарии приемлемы. Соблюдать вежливость к целям.
- **Проверено (v1.9.2)**: песочница клонирует репо, подтягивает БД из LFS
  (бинарник git-lfs 3.5.1), ставит зависимости и выполняет скрипт; результаты
  скачиваются в downloads/. SDK v2: `Sandbox.create()` / `sb.kill()`.

---

## Часть C: CircleCI (30 000 кредитов/мес бесплатно)

### Статус подключения (август 2026) — ✅ РАБОТАЕТ
- `.circleci/config.yml` — job `worker` с параметрами (JOB/SHARD/SHARD_TOTAL/BATCH/PORTS),
  выбор задачи: scan / audit_raw / audit_browser / internetdb / probe; LFS-pull БД.
- Новый токен `CCIPAT_...` (аккаунт JoTalbot) — полные права: `POST /pipeline` → создаёт pipeline.
- **Deploy key** для checkout приватного репо:
  1. `ssh-keygen -t ed25519 -f /tmp/circle_deploy`
  2. GitHub: `POST /repos/JoTalbot/scan/keys` (deploy key, read_only) — токеном ghp_...
  3. CircleCI: `POST /api/v1.1/project/gh/JoTalbot/scan/ssh-key` с hostname=github.com, private_key
- Проверено: pipeline #2 (internetdb) — success; pipeline #4 (скан шарда через dispatch) — success за 66 сек.
- Запуск:
  ```bash
  curl -s -X POST -H "Circle-Token: $TOKEN" -H "Content-Type: application/json" \
    -d '{"branch":"main","parameters":{"JOB":"internetdb"}}' \
    https://circleci.com/api/v2/project/gh/JoTalbot/scan/pipeline
  ```

### Запуск через dispatch.py (после исправления токена)
```bash
python3 dispatch.py scan --batch 100000 --shards 4 --parallel
# шарды распределятся: circleci → e2b → local
```
- Бесплатный план: 30 000 кредитов/мес (~3 000 мин Linux medium).
- OSS-проекты: 400 000 кредитов/мес (у нашего репо есть лицензия — можно подать заявку).
