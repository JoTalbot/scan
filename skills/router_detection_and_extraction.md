# 🛜 Детекция роутеров по HTTP-баннерам (Router Detection Engine)

## Контекст применения
Выделение роутеров/фаерволов/AP-устройств из результатов HTTP-сканирования (порт 80): как в реальном времени (во время скана), так и ретроспективно — по уже накопленным баннерам. Результат сохраняется в отдельную таблицу `scan_routers` и экспортируется в `data/routers/`.

## Входные данные и предварительные требования
- `isp_cidr.db` с таблицей `scan_results` (поля: `server_header`, `title`, `banner`).
- Файлы: `router_detect.py` (движок), `extract_routers.py` (ретроспектива), патчи в `port_scanner.py` и `sync_manager.py`.

## Пошаговый алгоритм
1. **Детекция** — `router_detect.detect_router(server_header, title, banner)` → `dict | None`:
   `{vendor, model, device_type, confidence, matched_on}`.
2. **Приоритет источников:** server_header → WWW-Authenticate `realm` → `<title>` → баннер-тело.
3. **Fallback-логика:** generic-сервер (medium, напр. `micro_httpd`) не возвращается сразу — сначала проверяются realm/title на более специфичную сигнатуру (напр. Zyxel high).
4. **Во время сканирования:** `port_scanner.py` вызывает детектор в `scan_single_target`, `flush()` пишет в `scan_routers` (INSERT OR REPLACE по `ip`).
5. **Ретроспектива:** `python3 extract_routers.py` — проходит по `scan_results WHERE has_banner=1`, пропуская IP уже в `scan_routers`; `--ip X` для одного адреса, `--no-export` без CSV.
6. **Экспорт:** `sync_manager.py` выгружает полный инвентарь в `data/routers/scan_routers_<agent>_<ts>.csv.gz` и пушит на GitHub.

## Таблица scan_routers
Ключевые поля: `ip` (UNIQUE), `vendor`, `model`, `device_type` (router/firewall/access_point), `confidence` (high/medium), `matched_on` (server_header/realm/title/banner), `http_status`, `server_header`, `title`, `banner`, `asn`, `isp_name`, `country_code`, `detected_at`, `agent_id`.
Индексы: vendor, model, asn, country_code, confidence.

## Критичные правила, чтобы не было ложных срабатываний
- **НЕ матчить голые слова вендоров в теле баннера** (banner): футеры CDN/хостингов (CloudFront, LiteSpeed, "platform: hostinger") содержат "huawei", "cisco", "h3c", "hp" и т.п. → правило `BANNER_RULES` только по очень специфичным фразам ("routeros router configuration page", "web-based configurator").
- **`hws` ≠ роутер** — это Hostinger (`platform: hostinger` в ответе).
- **"Cisco Umbrella"** — DNS-сервис, не роутер (паттерн Cisco требует `cisco-ios|cisco-isr|ios-xe` и т.п.).
- **Word boundaries обязательны:** подстрока `luci` матчит `lucide` (JS-библиотека иконок) и `Lucida Grande` (шрифт) → только `\bopenwrt\b|\bluci\b`.
- **Модели:** извлекаются regex'ами из realm/title (примеры: `TP-LINK Wireless Lite N Router WR741ND` → `WR741ND`; `Welcome to ZyXEL P-660HN-51` → `P-660HN-51`).
- **Порядок правил:** специфичные вендоры → фаерволы → generic (GoAhead, miniupnpd, micro_httpd, httpd = medium).

## Типичные ошибки
- Новые сигнатуры добавляются в `router_detect.py` → перезапуск `extract_routers.py` НЕ переобработает уже известные IP (они в `scan_routers`). Нужно: `DELETE FROM scan_routers WHERE vendor='...'` (или по IP) и перезапуск.
- Правки в `router_detect.py` синхронизируются на другие машины только через git push/pull.

## Критерии верификации
- `python3 router_detect.py` (self-test) — все тесты OK.
- `SELECT vendor, COUNT(*) FROM scan_routers GROUP BY vendor` — вендоры осмысленны, без "OpenWrt" на хостинг-страницах.
- `data/routers/scan_routers_*.csv.gz` создан и запушен; `git log` содержит коммит с `router_detect.py`.
