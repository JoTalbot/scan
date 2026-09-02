# 🌐 База Данных CIDR и Диапазонов IP Интернет-Провайдеров + RouterScan

Комплексная реляционная база данных (**SQLite**) официальных пулов IP-адресов,
автономных систем (ASN) и CIDR-подсетей интернет-провайдеров **Украины, США
и 49 стран Европы**, а также распределённая система **сканирования и аудита
роутеров** силами нескольких исполнителей (включая ИИ-агентов).

---

## 📌 Текущий статус

**Версия: 1.3.1 — maintenance release candidate.** Production 1.3.0 завершён.
Текущий batch добавляет bounded/rotating privacy-safe telemetry, aggregate observability
metrics API и отдельный privacy-safe dashboard для операционных графиков.

Машиночитаемый источник истины: `PROJECT_STATE.json`.

## 🛠️ Инструменты

| Инструмент | Назначение |
| :--- | :--- |
| `isp_tool.py` | Поиск по IP/ASN, экспорт правил (MikroTik, ipset, iptables, nginx, cisco) |
| `web_server.py` | Дашборд: CIDR-поиск, роутеры, гео-карта, статусы аудита и aggregate observability |
| `port_scanner.py` | Скан портов, детекция роутеров, шарды, приоритизация ISP |
| `router_detect.py` | Движок multi-signal детекции роутеров |
| `router_auth_check.py` | Авторизованный аудит конфигурации |
| `router_auth_browser.py` | Авторизованный аудит SPA-конфигураторов |
| `port_probe.py` | Дополнительные авторизованные probes |
| `bgp_looking_glass.py` | RIPE Stat: announced-prefixes и routing-status |
| `cve_check.py` | CVE-маппинг версий |
| `internetdb_enrich.py` | Shodan InternetDB enrichment |
| `dispatch.py` | Раздача задач по исполнителям |
| `resumable_dispatch.py` | Fail-closed resumable executor с shard-idempotency |
| `job_state.py` | Durable job/shard state |
| `observability.py` | Privacy-safe JSONL telemetry с bounded rotation и detection contract |
| `pipeline.sh` | Автоцикл pipeline |
| `openhands_agent.py` | ИИ-агент для задач разработки |
| `extract_routers.py` | Ретроспективная детекция |
| `generate_report.py` | Генерация отчёта |

## 🔐 Безопасность

- Активное сканирование выполняется только при явной авторизации и bounded scope.
- Credentials, tokens, API keys, private keys и raw HTTP artifacts не должны попадать в Git или публичные отчёты.
- Telemetry включается только через `SCAN_OBSERVABILITY_FILE` и рекурсивно редактирует чувствительные поля.
- `GET /api/observability` и `GET /api/observability/metrics` возвращают только агрегированные данные, без raw telemetry.
- Retry успешного shard идемпотентен; job завершается только после всех объявленных shard.

## 📊 Maintenance observability

Для telemetry можно задать:

```bash
export SCAN_OBSERVABILITY_FILE=/var/lib/routerscan/observability.jsonl
export SCAN_OBSERVABILITY_MAX_BYTES=5242880
export SCAN_OBSERVABILITY_ROTATIONS=3
```

Privacy-safe dashboard: `site_control/observability.html`.

## 🤖 Исполнители

| Исполнитель | Роль | Статус |
| :--- | :--- | :--- |
| `local` | основной сервер: скан + аудит | ✅ |
| `circleci` | шарды скана | ✅ |
| `e2b` | точечный аудит | ✅ |
| `codesandbox` | точечный аудит | ✅ |
| `openhands` | ИИ-агент: dev-задачи, анализ, PR | ✅ |
| `vercel` | serverless-аудит | ⏳ ждёт активации |

## ⚡ Быстрый старт

```bash
./pipeline.sh 100000
SCAN_MODE=dispatch SHARDS=6 ./pipeline.sh 100000
python3 dispatch.py dev --task-text "Добавь сигнатуры в router_detect.py и запушь"
python3 web_server.py
```

## 🧪 Проверки

```bash
.venv/bin/python -m pytest tests/ -v
python3 -m compileall -q .
```

CI проверяет поддерживаемые Python 3.10/3.11/3.12, security regression и repository policy gates.

## 📚 Документация

- `AGENTS.md` — протокол мультиагентной работы
- `PROJECT_STATE.json` — canonical project state
- `docs/BACKLOG.md` — backlog и принятые/непринятые улучшения
- `docs/OBSERVABILITY.md` — observability contract и runbook
- `docs/MAINTENANCE_OBSERVABILITY.md` — bounded telemetry, rotation и SLO policy
- `docs/OBSERVABILITY_BASELINE.md` — production baseline
- `docs/DASHBOARD_CHARTS.md` — privacy-safe dashboard chart contract
- `docs/RELEASE_POLICY.md` — правила версий и выпуска
- `docs/RELEASE_NOTES_1.3.0.md` — production release notes
- `site_control/observability.html` — aggregate observability dashboard
- `skills/` — база скилов агентов
