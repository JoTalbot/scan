# 🔑 Аудит заводских паролей роутеров (строгая верификация)

## Контекст применения
Проверка роутеров из таблицы `scan_routers` на заводские/популярные пароли с гарантией отсутствия ложных срабатываний. Результат — только строго верифицированные пары логин/пароль в отдельной таблице `router_credentials`.

## Входные данные и предварительные требования
- `isp_cidr.db` с таблицей `scan_routers` (поля `ip`, `port`, `vendor`, `model`, `banner`).
- `router_auth_check.py` + `data/creds/router_default_creds.csv` (расширяемый список `vendor,username,password`).
- Порядок запуска: `git pull --rebase` → `python3 agent_sync.py lock ...` → скрипт → `complete` → `sync_manager.py`.

## Пошаговый алгоритм
1. `python3 router_auth_check.py --dry-run` — список необработанных роутеров (`auth_checked=0`).
2. `python3 router_auth_check.py --concurrency 20 --timeout 5` — полный прогон.
3. Успехи — в `router_credentials`; каждый роутер помечается `auth_checked=1` + `auth_result` (напр. `verified:admin::basic`, `basic-no-match`, `no-verifiable-channel`, `unreachable`).
4. `python3 sync_manager.py "<AGENT>"` — экспорт `data/creds/router_credentials_*.csv.gz` + пуш.

## КРИТИЧНО: как отличить реальный успех от ложного
Наивный критерий «статус 2xx = успех» ДАЁТ МАССУ ЛОЖНЫХ СРАБАТЫВАНИЙ: MikroTik WebFig, Zyxel Web-Based Configurator, SonicWALL и др. отдают страницу логина с кодом 200 **без всякой авторизации**. Первая версия так нашла 25 «успехов» — все оказались фальшивыми.

**Строгие каналы (fingerprint → проверка):**
- **Basic (RFC 7617):** сначала GET / без авторизации — ОБЯЗАТЕЛЬНО 401 + `WWW-Authenticate: Basic`. Затем пары с Authorization header → успех только при 2xx/3xx. Если без пароля 200 — канал невалиден (`no-verifiable-channel`).
- **LuCI/OpenWrt:** GET /cgi-bin/luci/ должен иметь заголовок `X-LuCI-Login-Required: yes` + поле `luci_username`. POST `luci_username=..&luci_password=..` (+ `token` из формы при наличии). Успех ТОЛЬКО когда в ответе исчез `X-LuCI-Login-Required` (открылась панель) или 3xx на luci.
- Всё остальное (JS-формы без API, прокси, CDN) → помечается `no-verifiable-channel`, пары НЕ записываются.

## Структура списка паролей
- `VENDOR_DEFAULTS` в скрипте: заводские пары по вендору (MikroTik admin/(пусто), TP-Link admin/admin, Zyxel admin/1234, SonicWALL admin/password, OpenWrt root/(пусто), Ubiquiti ubnt/ubnt, Huawei telecomadmin/admintelecom и т.д.).
- `GENERIC_POPULAR`: 16 топ-пар на каждый роутер (admin/1234, admin/password, root/root и т.п.).
- Расширение: `data/creds/router_default_creds.csv` (строки `vendor,user,pass`), читается автоматически.

## Эмпирические выводы (проверено на 39 реальных устройствах)
- MikroTik «RouterOS» на порту 80 — чаще веб-прокси (`Mikrotik HttpProxy`, jsproxy → 404), админка не торчит в WAN → канал отсутствует.
- Zyxel / SonicWALL — JS-конфигураторы, API логина нет → `no-verifiable-channel`.
- DSL-модемы (realm "Broadband Router") — честный Basic, но в массе закрыты не-заводскими паролями → `basic-no-match`.
- Итог: 0 верифицированных пар из 39 — это корректный результат, а не ошибка инструмента.

## Типичные ошибки
- Запись «успеха» по одному коду 200 — всегда перепроверяйте: GET без пароля должен давать 401/403.
- Сброс для повторного прогона: `DELETE FROM router_credentials; UPDATE scan_routers SET auth_checked=0, auth_result=NULL;`
- Новые колонки (`auth_checked`, `auth_result`) добавляются автоматически в `init_db()` — при ручных SQL-правках учитывайте.
- Chunked-ответы LuCI: успех определяется по заголовку, парсить тело не нужно.
- После прогона всегда `cleanup_temp_files()` (встроен) — WAL/SHM/__pycache__ не должны попадать в git.

## Критерии верификации
- На локальном стенде с Basic-сервером (401-challenge): пара admin/(пусто) находится, неправильные — нет.
- В `router_credentials` нет записей с `auth_method` при `no-verifiable-channel`.
- `SELECT auth_result, COUNT(*) FROM scan_routers GROUP BY auth_result` — осмысленное распределение.
- Git-коммит содержит `router_auth_check.py`, экспорт `data/creds/`.
