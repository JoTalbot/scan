# 📊 Ежедневный отчёт — RouterScan Project

**Сформирован:** 2026-08-30 10:16 UTC

## 📈 Общая статистика

| Метрика | Значение |
| :--- | :---: |
| Просканировано IP | 8,094,738 |
| Веб-баннеров | 100,063 |
| Роутеров обнаружено | 1,028 |
| Проверено raw-каналами | 1,028 |
| Проверено браузером | 586 |
| Найдено пар | 7 |

## 🛜 Топ-10 роутеров по вендорам

| Вендор | Кол-во |
| :--- | :---: |
| MikroTik | 347 |
| Generic DSL Router | 120 |
| micro_httpd | 104 |
| OpenWrt | 73 |
| Zyxel | 61 |
| SonicWALL | 54 |
| TP-Link | 49 |
| httpd | 45 |
| Keenetic | 41 |
| Ubiquiti | 41 |

### 🆕 Последние 10 обнаруженных роутеров

| IP | Вендор | Порт | Обнаружен |
| :--- | :--- | :---: | :--- |
| 83.175.139.64 | httpd | 8080 | 2026-08-25T16:06:42Z |
| 81.161.61.64 | MikroTik | 80 | 2026-08-25T16:06:41Z |
| 185.241.236.192 | MikroTik | 80 | 2026-08-25T16:06:40Z |
| 141.98.251.64 | MikroTik | 80 | 2026-08-25T16:06:26Z |
| 141.98.248.128 | Cisco | 80 | 2026-08-25T16:06:26Z |
| 192.109.217.144 | MikroTik | 80 | 2026-08-25T16:06:23Z |
| 194.55.184.160 | MikroTik | 80 | 2026-08-25T16:06:22Z |
| 69.49.82.224 | Zyxel | 8080 | 2026-08-25T16:06:20Z |
| 38.50.214.128 | Generic DSL Router | 80 | 2026-08-25T16:06:17Z |
| 216.51.167.192 | Generic DSL Router | 80 | 2026-08-25T16:06:16Z |

## 🔍 Статусы аудита (raw)

| Статус | Кол-во |
| :--- | :---: |
| no-verifiable-channel | 574 |
| basic-no-match | 168 |
| rest-no-match | 143 |
| mikrotik_api-no-match | 78 |
| luci-no-match | 24 |
| sonicwall-no-match | 23 |
| unreachable | 10 |
| verified:admin:admin:basic | 4 |
| zyxel-no-match | 2 |
| verified:admin::basic | 1 |
| verified:admin:1234:basic | 1 |

## 🔑 Найденные пары

| IP | Вендор | Логин | Пароль | Метод | Дата |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 185.43.10.128 | httpd | admin | admin | basic | 2026-08-25T16:06:55Z |
| 38.124.153.112 | NETGEAR | admin | (пусто) | basic | 2026-08-25T14:46:39Z |
| 185.148.159.64 | NETGEAR | admin | admin | basic | 2026-08-25T14:46:38Z |
| 217.177.176.64 | NETGEAR | admin | admin | basic | 2026-08-25T10:45:51Z |
| 185.209.41.80 | GoAhead | admin | admin | browser | 2026-08-25T10:21:23Z |
| 38.148.85.0 | NETGEAR | admin | admin | basic | 2026-08-25T08:31:32Z |
| 151.237.137.224 | httpd | admin | 1234 | basic | 2026-08-25T08:31:26Z |

## 🌐 Топ Web-серверов

| Server | Кол-во |
| :--- | :---: |
| (hidden) | 17940 |
| nginx | 11783 |
| CloudFront | 11184 |
| cloudflare | 9778 |
| AkamaiGHost | 7538 |
| Apache | 5919 |
| nginx/1.24.0 (Ubuntu) | 2536 |
| LiteSpeed | 2227 |
| Caddy | 2156 |
| nginx/1.18.0 (Ubuntu) | 1743 |

## 🛡️ CVE — приоритеты

Приоритизированный разбор CVE по обнаруженным роутерам: [docs/CVE_PRIORITY.md](docs/CVE_PRIORITY.md)

---
*Авто-отчёт, генерируется GitHub Actions ежедневно.*