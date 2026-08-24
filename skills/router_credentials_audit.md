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

**Строгие каналы (fingerprint → проверка, приоритет: basic → rest → luci):**
- **Basic (RFC 7617):** сначала GET / без авторизации — ОБЯЗАТЕЛЬНО 401 + `WWW-Authenticate: Basic`. Затем пары с Authorization header → успех только при 2xx/3xx. Если без пароля 200 — канал невалиден (`no-verifiable-channel`).
- **REST (MikroTik RouterOS v7):** `GET /rest/ip/address` → 401 + `WWW-Authenticate: Basic`. WebFig при этом отдаёт 200 на /, поэтому GET / бесполезен для MikroTik. Успех = 2xx на /rest/ip/address с парой. Проверено: без REST-канала MikroTik необоснованно уходили в no-verifiable-channel.
- **Zyxel (login-page.cgi, P-660HN-стиль):** форма на главной с полями `AuthName`, `AuthPassword` (hidden), `Display`; пароль хэшируется JS в MD5. Успех = POST → 302 на НЕ-login-страницу (каталог /login/ ОК, login-page.cgi/login.cgi/login.html — нет) ИЛИ 200 без маркеров (login-page/Welcome/Please enter/Web Configurator). Внимание: редирект на /login/home-page.cgi — это УСПЕХ (каталог /login/ не исключает!).
- **SonicWALL (auth.cgi, CHAP):** форма /auth1.html (param1 = challenge, id). digest = MD5(id + пароль + challenge) по ASCII-байтам. POST /auth.cgi с id/uName/digest/pass="". ВАЖНО: auth.cgi ВСЕГДА отвечает 200 «Page Redirecting» (и при успехе, и при неудаче). Настоящий результат — в теле: `var sessIdStr = "<sid>"` — "null" = неудача, любое другое значение = УСПЕХ. Никогда не считать 200-без-формы успехом (это даёт ложные срабатывания!).
- **LuCI/OpenWrt:** GET /cgi-bin/luci/ должен иметь `X-LuCI-Login-Required: yes` + поле `luci_username`. POST `luci_username=..&luci_password=..` (+ `token` из формы при наличии). Успех ТОЛЬКО при: (а) 3xx-редиректе на luci (стоковый OpenWrt), либо (б) 200 + Set-Cookie `sysauth` + отсутствии login-required (кастомные форки). Просто "нет заголовка login-required" — НЕ критерий успеха!
- Всё остальное (JS-формы без API, прокси, CDN) → помечается `no-verifiable-channel`, пары НЕ записываются.
- **Важно:** `raw_request` читает ответ до EOF/дедлайна — chunked-ответы (LuCI) могут приходить несколькими TCP-сегментами; одно чтение обрезает тело и ломает детекцию luci_username.

## Уроки из реальных ложных срабатываний (обязательно учитывать)
1. **SonicWALL «Page Redirecting»:** auth.cgi отвечает 200 с одинаковой страницей на верный И неверный пароль. Критерий «200 без формы» дал ложный admin/password! Только `sessIdStr != "null"` — валидный признак.
2. **IP-флапы:** 91.148.140.144 менял содержимое в течение минут (Basic-роутер → Microsoft-IIS → китайская страница). Находка «admin/admin» была валидна в момент проверки, но IP переиспользован. Для динамических IP результаты нестабильны — перепроверять.
3. **Всегда ручная верификация** каждой найденной пары: без пароля → 401/форма, с паролем → консоль/редирект. Если ответы идентичны — критерий слабый, чинить, а не записывать.
4. Zyxel-редирект на /login/home-page.cgi содержит "login" — НЕ исключать весь путь с "login", только login-page.cgi/login.cgi/login.html.

## Как доказывается, что проверки без ошибок
1. **Позитивный контроль:** локальный стенд (Basic-сервер, пара `admin`/(пусто)) → скрипт ОБЯЗАН найти пару. Если не находит — скрипт сломан. Прогонять при каждом изменении логики.
2. **Стабильность:** 2+ последовательных `--force` прогона должны давать ИДЕНТИЧНОЕ распределение `auth_result`. Расхождение = флаки (сеть, обрезка ответов).
3. **Отсутствие ложных срабатываний:** пара записывается только если тот же endpoint без авторизации отдаёт 401, а с парой — 2xx/3xx. Устройства с JS-логином (200-страница без auth) никогда не дают "успех".
4. **Диагностика каналов:** при подозрении на пропуск канала — зондировать вручную (GET /, /rest/ip/address, /webfig/, /jsproxy/login, /cgi-bin/luci/) и добавлять реальные API-каналы, а не ослаблять критерии.

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
