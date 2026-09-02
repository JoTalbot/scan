# 📊 Ежедневный отчёт — RouterScan Project

**Сформирован:** 2026-09-02 09:17 UTC

## 📈 Общая статистика

| Метрика | Значение |
| :--- | :---: |
| Просканировано IP | 8,094,738 |
| Веб-баннеров | 100,063 |
| Роутеров обнаружено | 1,028 |
| Проверено raw-каналами | 1,028 |
| Проверено браузером | 586 |
| Обнаружено credential findings | 7 |

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

## 🔍 Статусы аудита

Публичный отчёт содержит только агрегированные статусы. Individual targets, credentials, authorization material и raw HTTP evidence намеренно исключены.

| Статус | Кол-во |
| :--- | :---: |
| no-verifiable-channel | 574 |
| basic-no-match | 168 |
| rest-no-match | 143 |
| mikrotik_api-no-match | 78 |
| luci-no-match | 24 |
| sonicwall-no-match | 23 |
| unreachable | 10 |
| verified-classification | 6 |
| zyxel-no-match | 2 |

## 🔐 Credential findings

В исходных операционных данных были обнаружены 7 credential findings. В публичном отчёте они представлены только количеством и классификацией. IP-адреса, логины, пароли и методы аутентификации удалены из публичного артефакта.

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
*Публичный авто-отчёт. Live targets, credentials, raw HTTP artifacts и private telemetry не публикуются.*
