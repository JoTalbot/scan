# 🌐 Браузерная проверка паролей роутеров (Playwright / SPA-канал)

## Контекст применения
Проверка роутеров, чей логин — JavaScript-SPA/апплет без пригодного HTTP-API (`auth_result = 'no-verifiable-channel'`): новые Zyxel, SonicWALL sonicui, MikroTik WebFig, Keenetic. Запускается headless Chromium, который рендерит форму, сабмитит пары и наблюдает DOM.

## Входные данные и предварительные требования
- `router_auth_browser.py` + venv: `python3 -m venv .venv && PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright .venv/bin/pip install playwright==1.62.0` (.venv в .gitignore).
- Таблица `scan_routers` (browser_checked/browser_result колонки добавляются автоматически).
- Переиспользует базу паролей `router_auth_check.py` (VENDOR_DEFAULTS + GENERIC_POPULAR + data/creds/*.csv).

## Пошаговый алгоритм
1. `python3 agent_sync.py lock ...`
2. Список целей: `.venv/bin/python router_auth_browser.py --dry-run --only-no-channel`
3. Прогон: `.venv/bin/python router_auth_browser.py --only-no-channel --pairs 15 --concurrency 2 --timeout 10 --wait 4` (в фоне: `setsid nohup ... > logs/browser_audit.log 2>&1 < /dev/null &`; python буферизует stdout — прогресс появляется блоками).
4. Точечная перепроверка: `--ip X.X.X.X`.
5. Ручная верификация КАЖДОЙ находки (см. ниже), затем `agent_sync.py complete` + `sync_manager.py` (экспортирует router_credentials + скриншоты в data/routers/shots/).

## КРИТИЧНО: отложенная аутентификация (MikroTik WebFig) — 4-я итерация
- MikroTik WebFig v6: кнопка логина — `<a onclick="dologin()">` (НЕ input[type=submit]!), поля — по `id` (name/password), HTML-формы нет, Enter не сабмитит.
- dologin() ВСЕГДА редиректит на /webfig/ (и при верном, и при неверном пароле) и показывает "Loading".
- Реальная проверка — отложенная (~15 сек): при неверном пароле страница возвращается на / с формой и сообщением об ошибке.
- ❌ Критерий «форма исчезла + reload» дал ЛОЖНУЮ находку admin/admin: скрипт фиксировал момент Loading.
- ✅ ИСПРАВЛЕНИЕ: после исчезновения формы ждать ещё 15 сек, затем проверять: форма вернулась? текст ошибки (authentication failed|invalid user|failed to log)? Если да — fail.
- Проверять наличие submit-кнопки; если её нет (только <a onclick>), вызывать JS-функцию через page.evaluate.

## КРИТИЧНО: критерий успеха (3 итерации отладки + отложенная аутентификация)
Наивные варианты дают ложные находки:
- ❌ «форма исчезла через N мс» — перерисовка страницы/редирект-заглушка.
- ❌ + «reload не вернул форму» — SonicWALL lockout-страница и заглушки не содержат формы И слов ошибки.
- ✅ **ФИНАЛЬНЫЙ**: success только если ВСЕ условия:
  1. поле пароля исчезло после сабмита;
  2. на странице нет текста ошибки (incorrect|invalid|wrong password|login failed|authentication failed|access denied|unauthor|error|**lockout|locked out|too many|blocked|failed**|неверн|ошибк|заблокир);
  3. reload не вернул форму (сессия держится);
  4. страница содержит ПРИЗНАКИ КОНСОЛИ (dashboard|status|system|logout|sign out|firewall|interface|management|console|settings|network|welcome|home|license|uptime|webfig|routeros).

## Обязательная ручная верификация находок
- Открыть устройство ЧИСТОЙ попыткой (без предварительных неверных паролей!).
- MikroTik WebFig блокирует аккаунт после нескольких неудачных попыток; SonicWALL sonicui — полноценный lockout («Too many login attempts... locked out») на 5-10+ минут. Одна-две неверные попытки = потеря возможности проверить.
- Проверить: форма исчезла, URL консоли (/webfig/, /sonicui/...), контент после reload.

## Типичные ошибки и как их обходить
- **Ложный success на SonicWALL**: submit → редирект на lockout/заглушку (форма нет, слов ошибки нет) → критерий 2 засчитывал. Лечится признаками консоли (пункт 4).
- **WebFig MikroTik**: форма во фрейме? Нет — на /webfig/ после входа "Loading" + консоль; но блокировки аккаунта — реальность. Соблюдать вежливость: max 1-2 попытки на устройство в минуту.
- **SonicWALL новые модели**: auth1.html → 404, логин ТОЛЬКО через https (sonicui/7/login/). В probe обязательно: http → fallback-пути → https.
- **python буферизация**: при перенаправлении в файл прогресс виден блоками — не паниковать, проверять `ps aux | grep router_auth_browser`.
- **kill эмуляторов/процессов**: не использовать pkill с паттерном, который есть в собственной командной строке (убивает сам bash) — использовать python-скрипт по /proc с исключением собственного PID.

## 🚀 FAST-режим (для больших партий роутеров)
- `router_auth_check.py --fast`: только вендор-специфичные пары + TOP-5 общих (вместо 56) — в ~10 раз меньше запросов на устройство. Разумно, т.к. по модели известно, какие пары реально возможны (философия Router Scan by Stas'M: 1-5 пар на модель, а не дробовик).
- `router_auth_browser.py`: `--pairs 8 --concurrency 4 --timeout 7 --wait 2.5` + **умный delayed-auth**: 15-секундная проверка отложенной аутентификации применяется ТОЛЬКО к MikroTik (единственный вендор с WebFig-задержкой); остальные вендоры аутентифицируются синхронно → без простоя.
- Итог на партии 99 SPA-устройств: **~22 мин** вместо ~2-3 часов, строгость сохранена (0 ложных срабатываний, подтверждено эмуляторами).
- Смотреть прогресс: `tail -f logs/browser_fast.log` (запускать с `-u`).
- При `browser-session-lost` (форма не вернулась на wrong-контроле) — устройство НЕ записывается (нестабильно), не засчитывать как находку.

## Критерии верификации
- Позитивные эмуляторы (HTML-форма / form+iframe / чистый SPA с fetch+cookie-сессией) — все 3 находятся.
- Ручная проверка каждой находки одной чистой попыткой.
- `SELECT browser_result, COUNT(*) FROM scan_routers GROUP BY browser_result` — осмысленно; в router_credentials только ручно подтверждённые пары.
