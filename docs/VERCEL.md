# ▲ Vercel Worker для RouterScan (статус: подготовлен, нужна активация аккаунта)

## Что готово
- `vercel_worker/api/audit.js` — serverless-функция для аудита списка IP:
  - `POST /api/audit` `{targets: ["1.2.3.4",...], mode: "http"|"reach"}`
  - http: HTTP-баннер (status, server, len) на порту (по умолчанию 80)
  - reach: TCP-проверка портов 80/443/8080/8443
  - до 50 целей на запрос, таймаут 3 с/цель
- `vercel_worker/vercel.json` — maxDuration 60 с, memory 1024 МБ

## Статус подключения (август 2026)
- Токен `vck_...` (аккаунт `dedsinfo-6967`, dedsinfo@gmail.com) — **валиден для `/v2/user`**,
  но аккаунт помечен `limited: True`:
  - ❌ `POST /v10/projects` → "You don't have permission to create the project"
  - ❌ `POST /v13/deployments` → "forbidden"
  - ❌ Vercel CLI `--token` → "not valid"
  - ✅ `GET /v2/user` работает
- Причина: ограниченный аккаунт (не подтверждена оплата/верификация).
  Vercel лимитирует такие аккаунты до подтверждения.

## Как активировать (на выбор)
1. **Web-интерфейс**: зайти в vercel.com → Settings → подтвердить email/аккаунт,
   при необходимости добавить карту (Hobby бесплатен, карта для верификации).
2. **CLI**: `npx vercel login dedsinfo@gmail.com` → пройти device-код в браузере,
   затем `npx vercel link` в vercel_worker/ и `npx vercel --prod`.

## После активации
```bash
cd /root/scan/vercel_worker
export VERCEL_TOKEN="vck_..."
npx vercel --token "$VERCEL_TOKEN" --prod --yes

# тест
curl -X POST https://<project>.vercel.app/api/audit \
  -H "Content-Type: application/json" \
  -d '{"targets":["8.8.8.8","1.1.1.1"],"mode":"reach"}'
```

## Лимиты Vercel Hobby (для планирования)
| Ресурс | Hobby |
| :--- | :--- |
| Serverless functions | 1M invocations/мес |
| Время выполнения | до 300 с (Hobby), maxDuration в vercel.json |
| Память | до 1024 МБ |
| Bandwidth | 100 ГБ/мес |
| Build minutes | 6000/мес |
| Коммерческое использование | ❌ только некоммерческое (fair use) |

## Интеграция в dispatch.py (когда активируется)
```python
# в TASKS добавить:
#   "vercel_probe": {"cmd": "...", "vercel_ok": True}
# функция run_vercel():
#   1) берёт до 50 целей из БД
#   2) POST на https://<project>.vercel.app/api/audit
#   3) сохраняет результаты в logs/dispatch/vercel.log
```

## ⚠️ Примечания
- Vercel Functions — не для постоянных сканов; используйте для точечного аудита (как E2B).
- IP запросов — датацентровые Vercel; для распределения плюс.
- ToS Hobby: некоммерческое использование.
