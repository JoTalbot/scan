# 💻 CodeSandbox Worker для RouterScan

## Статус: ✅ РАБОТАЕТ (август 2026)

CodeSandbox подключён как исполнитель для точечного аудита целей
(аналогично E2B, но с другим пулом IP).

## Что работает
- `csb_audit.js` — Node-скрипт (SDK `@codesandbox/sdk` v2.4.2):
  1. Создаёт песочницу (Universal template, Python 3.10 + git + curl)
  2. Ждёт инициализацию ~20 сек (обязательно!)
  3. Загружает цели через base64 (echo | base64 -d)
  4. Клонирует репо в /tmp/scan
  5. Запускает `e2b_targets_audit.py` (mode http/reach)
  6. Выводит JSON-результаты

- `dispatch.py csb_probe --batch N` — берёт N непроверенных роутеров из БД,
  отдаёт в песочницу CodeSandbox, результат в logs/dispatch/csb_probe.log

## Проверено end-to-end
- Аудит 3 IP: 94.249.218.128 (HTTP 200), 5.32.177.224 (200), 5.32.177.96 (200) — rc=0
- reach-режим: 8.8.8.8 → открыт 443
- Время: ~5-6 мин на партию (20с инициализация + ~5 мин аудит)

## Требования
- Токен: https://codesandbox.io/t/api → `CSB_API_KEY` (в .env: CODESANDBOX_TOKEN)
- SDK: `npm install --no-save @codesandbox/sdk` в /root/scan
- Лимиты free: песочницы хибернизируются; время жизни ограничено

## Команды
```bash
# через диспетчер (непроверенные роутеры из БД):
python3 dispatch.py csb_probe --batch 10

# напрямую:
CSB_API_KEY=$(grep CODESANDBOX_TOKEN .env | cut -d= -f2) \
  node csb_audit.js --targets "1.2.3.4,5.6.7.8" --mode http
CSB_API_KEY=... node csb_audit.js --file targets.txt --mode reach
```

## ⚠️ Примечания
- Песочница создаётся с задержкой инициализации — `sleep 20000` обязателен
- `session.files.write` нестабилен — используем base64 через команду
- Время партии ~5-6 мин: планировать батчи по 10-20 целей
