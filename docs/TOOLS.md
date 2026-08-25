# Дополнение к README.md — инструменты и автоматизация (v1.8+)

## 🛠️ Инструменты сканирования и аудита

| Инструмент | Назначение |
| :--- | :--- |
| `port_scanner.py` | Скан HTTP-портов (80/8080/8443), детекция роутеров, мультимашинные шарды (`--shard i/N`), приоритизация провайдеров (`--isp-words`), извлечение realm |
| `router_detect.py` | Движок детекции роутеров (35+ вендоров) по server_header/realm/title/banner |
| `router_auth_check.py` | Raw-аудит паролей: Basic, REST (MikroTik v7), MikroTik API (8728), Zyxel MD5-форма, SonicWALL CHAP, LuCI; `--fast` режим |
| `router_auth_browser.py` | Playwright-аудит SPA-конфигураторов (headless Chromium), строгий критерий успеха + отложенная аутентификация WebFig |
| `router_ssh_telnet_audit.py` | SSH/Telnet аудит открытых портов 22/23 (paramiko + telnetlib) |
| `port_probe.py` | Доп. порты (8291/8728/7547/8080/8443/23/22) + raw SNMPv1 (public/private, 4 OID) |
| `bgp_looking_glass.py` | RIPE Stat API: announced-prefixes, routing-status, `--update-db` (добавление новых BGP-префиксов в БД) |
| `cve_check.py` | CVE-маппинг версий обнаруженных роутеров → CVE_REPORT.md |
| `verify_findings.py` | Double-check найденных пар (динамические IP) |
| `extract_routers.py` | Ретроспективная детекция роутеров по старым сканам |
| `generate_report.py` | Генерация REPORT.md (статистика/вендоры/аудит/пары) |
| `web_server.py` | Дашборд (порт 8899): CIDR-поиск + роутеры + гео-карта + статусы аудита |
| `pipeline.sh` | Автоцикл: скан → аудит → sync → уведомление (cron каждые 6ч) |
| `start_workers.sh` | Мультимашинный скан: N шардов локально или по SSH |
| `sync_manager.py` | Синхронизация: чанки сканов, инвентарь роутеров, пары, БД (gzip), пуш через Git LFS |

## ⚡ Быстрый старт

```bash
# 1. Скан 100k на 3 портах (~100 сек)
ulimit -n 65535 && python3 port_scanner.py run --batch 100000 --concurrency 1000 --timeout 1.0 --ports 80,8080,8443

# 2. Аудит новых роутеров
python3 router_auth_check.py --fast --concurrency 30 --timeout 4
.venv/bin/python -u router_auth_browser.py --only-no-channel --pairs 8 --concurrency 4 --timeout 7 --wait 2.5

# 3. Синхронизация на GitHub (Git LFS для БД)
python3 sync_manager.py "Agent-Arena-01"

# 4. Полный автоцикл (или cron каждые 6ч)
./pipeline.sh 100000
```

## 🗄️ База данных
- `isp_cidr.db` — SQLite (~600 МБ): `cidr_blocks` (508k+ префиксов), `ip_ranges`, `providers`, `scan_results` (UNIQUE ip+port, realm), `scan_routers` (327 устройств, статусы аудита, cves, admin_port, extra_ports), `router_credentials`, `device_ports`, `snmp_results`, `snmp_data`
- В git — через **Git LFS** (`isp_cidr.db.gz`), raw БД локально (untracked)
- Бэкапы: `backups/isp_cidr_YYYYMMDD.db.gz` (ротация 7 дней, в pipeline)

## 🧪 Тесты
```bash
.venv/bin/python -m pytest tests/ -v   # 21 тест: детектор, пароли, SNMP, API
```

## 🔑 Аудит паролей — каналы
HTTP Basic · REST (MikroTik v7) · MikroTik API (8728, challenge+MD5) · Zyxel form (MD5) · SonicWALL CHAP · LuCI/OpenWrt · SSH · Telnet · SNMP — успехи в `router_credentials` (строгая верификация, 0 ложных срабатываний).

## 📈 Отчёты
- `REPORT.md` — ежедневно GitHub Actions (05:00 UTC)
- `CVE_REPORT.md` — уязвимые устройства по известным CVE
- Дашборд: `http://<host>:8899` (роутеры, гео-карта, статусы)
