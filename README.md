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
| `port_scanner.py` | Скан 3 портов (~1000 IP/сек), детекция роутеров, шарды, приоритизация ISP |
| `router_detect.py` | Движок детекции роутеров (35+ вендоров) |
| `router_auth_check.py` | Аудит паролей: Basic/REST/MikroTik API/Zyxel/SonicWALL/LuCI (fast-режим) |
| `router_auth_browser.py` | Playwright-аудит SPA-конфигураторов (строгий критерий) |
| `port_probe.py` | Доп. порты + raw SNMP (public/private, 4 OID) |
| `bgp_looking_glass.py` | RIPE Stat: announced-prefixes, routing-status, `--update-db` |
| `cve_check.py` | CVE-маппинг версий → CVE_REPORT.md |
| `internetdb_enrich.py` | Shodan InternetDB: порты/CVE/CPE без ключа (307 IP обогащено) |
| `dispatch.py` | **Раздача задач по 6 исполнителям** (см. ниже) |
| `pipeline.sh` | **Автоцикл**: скан → аудит → dispatch → sync (cron каждые 6 ч) |
| `openhands_agent.py` | ИИ-агент для задач разработки (пишет код, пушит сам) |
| `e2b_targets_audit.py` | Лёгкий аудит целей в E2B/CodeSandbox песочницах |
| `verify_findings.py` | Double-check найденных пар |
| `extract_routers.py` | Ретроспективная детекция по старым сканам |
| `generate_report.py` | Отчёт REPORT.md (GitHub Actions ежедневно) |

## 🤖 Исполнители (пул)

| Исполнитель | Роль | Статус |
| :--- | :--- | :--- |
| `local` | основной сервер: скан + аудит | ✅ |
| `circleci` | шарды скана (pipeline, 2 vCPU) | ✅ |
| `e2b` | точечный аудит целей (478 МБ) | ✅ |
| `codesandbox` | точечный аудит (Python 3.10) | ✅ |
| `openhands` | ИИ-агент: dev-задачи, анализ, PR | ✅ |
| `vercel` | serverless-аудит | ⏳ ждёт активации |

## ⚡ Быстрый старт

```bash
# 1. Полный автоцикл (скан 100k + аудит + push)
./pipeline.sh 100000

# 2. Распределённый скан через dispatch (6 шардов = ~600k за 5 мин)
SCAN_MODE=dispatch SHARDS=6 ./pipeline.sh 100000

# 3. Точечный аудит непроверенных роутеров
python3 dispatch.py csb_probe --batch 20
python3 dispatch.py e2b_probe --batch 20

# 4. Дать задачу ИИ-агенту
python3 dispatch.py dev --task-text "Добавь сигнатуры в router_detect.py и запушь"

# 5. BGP-обновление базы
python3 bgp_looking_glass.py --asn 3320 --update-db

# 6. Дашборд
python3 web_server.py   # http://<host>:8899
```

## 📈 Отчёты
- `REPORT.md` — ежедневный (GitHub Actions)
- `CVE_REPORT.md` — уязвимые устройства
- `internetdb_report.md` — порты/CVE по Shodan
- Дашборд: роутеры, гео-карта, статусы аудита

## 🧪 Тесты
```bash
.venv/bin/python -m pytest tests/ -v   # 21+ тест
```

## 📚 Документация
- `AGENTS.md` — протокол мультиагентной работы
- `skills/` — база скилов агентов
- `docs/TOOLS.md`, `docs/DISPATCH.md`, `docs/CODESPACES_E2B.md`,
  `docs/CODESANDBOX.md`, `docs/VERCEL.md`, `docs/COMPUTE_VECTORS.md`
