# 🌐 База Данных CIDR и Диапазонов IP Интернет-Провайдеров + RouterScan

Комплексная реляционная база данных (**SQLite**) официальных пулов IP-адресов,
автономных систем (ASN) и CIDR-подсетей интернет-провайдеров **Украины, США
и 49 стран Европы**, а также распределённая система **сканирования и аудита
роутеров** силами нескольких исполнителей (включая ИИ-агентов).

---

## 📊 Статистика (август 2026)

| Метрика | Значение |
| :--- | :--- |
| Просканировано IP | **3 550 000+** (порты 80/8080/8443) |
| Обнаружено роутеров | **433** |
| CIDR-блоков в базе | 508 879+ |
| Верифицированных пар | 0 (все проверенные устройства закрыты) |
| CVE-строк (InternetDB) | 436 |

---

## 🛠️ Инструменты

| Инструмент | Назначение |
| :--- | :--- |
| `isp_tool.py` | Поиск по IP/ASN, экспорт правил (MikroTik, ipset, iptables, nginx, cisco) |
| `web_server.py` | Дашборд (порт 8899): CIDR-поиск, роутеры, гео-карта, статусы аудита |
| `port_scanner.py` | Скан 3 портов, детекция роутеров, шарды, приоритизация ISP |
| `router_detect.py` | Движок детекции роутеров (35+ вендоров) |
| `router_auth_check.py` | Аудит паролей: Basic/REST/MikroTik API/Zyxel/SonicWALL/LuCI (fast-режим) |
| `router_auth_browser.py` | Playwright-аудит SPA-конфигураторов (строгий критерий) |
| `port_probe.py` | Доп. порты + raw SNMP (public/private, 4 OID) |
| `bgp_looking_glass.py` | RIPE Stat: announced-prefixes, routing-status, `--update-db` |
| `cve_check.py` | CVE-маппинг версий → CVE_REPORT.md |
| `internetdb_enrich.py` | Shodan InternetDB: порты/CVE/CPE без ключа |
| `dispatch.py` | Раздача задач по исполнителям |
| `resumable_dispatch.py` | Fail-closed resumable executor с shard-idempotency |
| `observability.py` | Privacy-safe JSONL lifecycle telemetry и detection contract |
| `web_server.py` | Агрегированная observability-панель через `/api/observability` |
| `pipeline.sh` | Автоцикл: скан → аудит → dispatch → sync |
| `openhands_agent.py` | ИИ-агент для задач разработки |
| `extract_routers.py` | Ретроспективная детекция по старым сканам |
| `generate_report.py` | Отчёт REPORT.md |

## 🔐 Observability

Telemetry включается только при заданном `SCAN_OBSERVABILITY_FILE`. В JSONL
пишутся lifecycle-события jobs/shards и безопасные результаты детекции.
Сырые цели, inventories, HTTP headers, authorization refs, credentials,
passwords, tokens, API keys и private keys в telemetry не попадают.

`GET /api/observability` отдаёт только aggregate event counts. Raw telemetry
через dashboard API намеренно недоступна.

Подробности: `docs/OBSERVABILITY.md`.

## 🤖 Исполнители (пул)

| Исполнитель | Роль | Статус |
| :--- | :--- | :--- |
| `local` | основной сервер: скан + аудит | ✅ |
| `circleci` | шарды скана | ✅ |
| `e2b` | точечный аудит целей | ✅ |
| `codesandbox` | точечный аудит | ✅ |
| `openhands` | ИИ-агент: dev-задачи, анализ, PR | ✅ |
| `vercel` | serverless-аудит | ⏳ ждёт активации |

## ⚡ Быстрый старт

```bash
./pipeline.sh 100000
SCAN_MODE=dispatch SHARDS=6 ./pipeline.sh 100000
python3 dispatch.py dev --task-text "Добавь сигнатуры в router_detect.py и запушь"
python3 bgp_looking_glass.py --asn 3320 --update-db
python3 web_server.py
```

Для локальной проверки telemetry:

```bash
export SCAN_OBSERVABILITY_FILE=/var/lib/routerscan/observability.jsonl
python3 -m pytest tests/ -q
```

## 📈 Отчёты
- `REPORT.md` — ежедневный
- `CVE_REPORT.md` — уязвимые устройства
- `internetdb_report.md` — порты/CVE по Shodan
- Дашборд: роутеры, гео-карта, статусы аудита и агрегированная telemetry

## 🧪 Тесты
```bash
.venv/bin/python -m pytest tests/ -v
```

## 📚 Документация
- `AGENTS.md` — протокол мультиагентной работы
- `PROJECT_STATE.json` — canonical project state
- `docs/BACKLOG.md` — backlog и принятые/непринятые улучшения
- `docs/OBSERVABILITY.md` — observability contract и runbook
- `skills/` — база скилов агентов
