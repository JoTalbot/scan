# 🌐 База Данных CIDR и Диапазонов IP Интернет-Провайдеров (Украина, США, Европа)

Комплексная реляционная база данных (**SQLite**), содержащая официальные пулы IP-адресов, автономные системы (ASN), диапазоны от начального до конечного IP (`start_ip` - `end_ip`), маски подсетей (`netmask`, `wildcard_mask`) и CIDR-подсети интернет-провайдеров и телеком-операторов **Украины**, **США** и всех **49 стран Европы**.

---

## 📊 Общая статистика базы данных

| Регион | Стран | Автономных систем (ASN) | IPv4 CIDR / Диапазонов | IPv6 CIDR / Диапазонов | Всего CIDR / Диапазонов | Выделено IPv4 адресов |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 🇺🇦 **Украина** | 1 | **1,592** | 5,869 | 969 | **6,838** | **8,258,301** |
| 🇪🇺 **Европа (все страны)** | 49 | **20,471** | 128,170 | 53,094 | **181,264** | **561,872,486** |
| 🇺🇸 **США (United States)** | 1 | **18,587** | 251,445 | 69,332 | **320,777** | **1,352,535,864** |
| **ИТОГО** | **51** | **40,650** | **385,484** | **123,395** | **508,879** | **1,922,666,651** |

---

## 📁 Содержимое репозитория

| Файл | Описание |
| :--- | :--- |
| **`isp_cidr.db`** | Основная база данных SQLite (89 МБ) с таблицами `cidr_blocks`, `ip_ranges`, `providers`, `countries`, представлениями и B-Tree индексами. |
| **`isp_tool.py`** | Утилита командной строки и Python-библиотека для поиска по IP/ASN, диапазонам и экспорта правил. |
| **`build_db.py`** | Скрипт сборки базы данных с нуля из дампов RIPE NCC и ARIN. |
| **`web_server.py`** | Интерактивный веб-дашборд с поиском, аналитикой и экспортом на порту `8000`. |
| **`AGENTS.md`** | Протокол и регламент для параллельной работы распределенных ИИ-агентов. |
| **`STATUS.md`** & **`agent_state.json`** | Живая матрица статуса текущих шагов и блокировок агентов. |
| **`agent_sync.py`** | Утилита координации шагов и автоматического сохранения скилов. |
| **`skills/`** | База формализованных навыков, полученных агентами при выполнении задач. |
| **`isp_cidr_ukraine.csv`** | Полный CSV-экспорт всех подсетей и диапазонов Украины (6,838 записей). |
| **`isp_top_providers.csv`** | Топ-500 провайдеров по объемам IP-адресов. |
| **`export_ukraine_cidrs_ipv4.txt`** | Текстовый список IPv4 CIDR Украины. |
| **`export_ukraine_cidrs_ipv6.txt`** | Текстовый список IPv6 CIDR Украины. |
| **`export_ukraine_mikrotik.rsc`** | Скрипт для роутеров MikroTik RouterOS (`/ip firewall address-list`). |
| **`export_ukraine_ipset.sh`** | Готовый скрипт для Linux `ipset`. |
| **`export_ukraine_nginx.conf`** | Конфигурационный блок `geo` для веб-сервера Nginx. |

---

## 🏛 Структура базы данных (`isp_cidr.db`)

### 1. Таблица `ip_ranges` (Диапазоны IP-адресов)
| Колонка | Тип | Описание |
| :--- | :--- | :--- |
| `cidr_id` | INTEGER PRIMARY KEY | Связь 1-к-1 с `cidr_blocks.id` |
| `start_ip` | TEXT NOT NULL | Начальный IP-адрес подсети (например, `5.248.0.0`) |
| `end_ip` | TEXT NOT NULL | Конечный IP-адрес подсети (например, `5.248.255.255`) |
| `start_ip_int` | INTEGER | Целочисленный начальный IPv4 (uint32) для быстрого поиска диапазона |
| `end_ip_int` | INTEGER | Целочисленный конечный IPv4 (uint32) |
| `netmask` | TEXT | Сетевая маска (например, `255.255.0.0` для IPv4 или `/48` для IPv6) |
| `wildcard_mask` | TEXT | Инверсная маска Cisco (например, `0.0.255.255` для IPv4) |

**Индексы:** `idx_range_range (start_ip_int, end_ip_int)`.

---

### 2. Таблица `cidr_blocks` (Подсети CIDR)
| Колонка | Тип | Описание |
| :--- | :--- | :--- |
| `id` | INTEGER PRIMARY KEY | Уникальный ID подсети |
| `cidr` | TEXT NOT NULL | CIDR подсеть (например, `5.248.0.0/16`) |
| `ip_version` | INTEGER NOT NULL | Версия IP (`4` или `6`) |
| `asn` | INTEGER | Номер автономной системы (ASN) |
| `country_code` | TEXT NOT NULL | Код страны (`UA`, `US`, `DE`...) |
| `total_ips` | INTEGER | Емкость подсети (количество адресов) |

**Индексы:** `idx_cidr_cidr`, `idx_cidr_asn`, `idx_cidr_cc`.

---

### 3. Таблица `providers` (Автономные системы и провайдеры)
| Колонка | Тип | Описание |
| :--- | :--- | :--- |
| `asn` | INTEGER PRIMARY KEY | Номер автономной системы |
| `as_name` | TEXT | Хэндл AS (например, `KSNET-AS`) |
| `org_name` | TEXT NOT NULL | Полное наименование провайдера / организации |
| `country_code` | TEXT NOT NULL | Код страны регистрации |
| `country_name_en` | TEXT NOT NULL | Название страны (EN) |
| `country_name_ru` | TEXT NOT NULL | Название страны (RU) |
| `region` | TEXT NOT NULL | Регион (`Ukraine`, `United States`, `Europe`) |
| `ipv4_cidr_count` | INTEGER | Количество IPv4 подсетей |
| `ipv6_cidr_count` | INTEGER | Количество IPv6 подсетей |
| `total_ipv4_ips` | INTEGER | Суммарное количество IPv4 адресов |

---

### 4. Представления `v_ip_ranges` и `v_cidr_details`
Предоставляют готовый объединенный доступ к подсетям, диапазонам, маскам, провайдерам и странам.

---

## 🛠 Примеры запросов к диапазонам IP

### Выборка диапазонов по конкретному провайдеру:
```sql
SELECT start_ip, end_ip, cidr, netmask, total_ips, isp_name, country_name_ru
FROM v_ip_ranges
WHERE asn = 15895
ORDER BY start_ip_int;
```

### Поиск диапазона, содержащего заданный IP (мгновенный бинарный поиск):
```sql
SELECT start_ip, end_ip, cidr, netmask, asn, isp_name, country_name_ru
FROM v_ip_ranges
WHERE ip_version = 4 
  AND start_ip_int <= 100139008 -- int(5.248.10.20)
  AND end_ip_int >= 100139008
LIMIT 1;
```

---

## 💻 CLI Команды `isp_tool.py`

```bash
# Просмотр диапазонов провайдеров Украины:
python3 isp_tool.py ranges --country UA --limit 20

# Проверка IP адреса с выводом диапазона и маски:
python3 isp_tool.py lookup 5.248.10.20

# Экспорт диапазонов в текстовый файл:
python3 isp_tool.py export --country UA --format ranges --out ua_ranges.txt
```
