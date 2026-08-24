# 🌐 База Данных CIDR Интернет-Провайдеров (Украина, США, Европа)

Комплексная реляционная база данных (**SQLite**), содержащая официальные пулы IP-адресов, автономные системы (ASN), диапазоны и CIDR-подсети интернет-провайдеров и телеком-операторов **Украины**, **США** и всех **49 стран Европы**.

---

## 📊 Общая статистика базы данных

| Регион | Стран | Автономных систем (ASN) | IPv4 CIDR подсетей | IPv6 CIDR подсетей | Всего CIDR | Выделено IPv4 адресов |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 🇺🇦 **Украина** | 1 | **1,592** | 5,869 | 969 | **6,838** | **8,258,301** |
| 🇪🇺 **Европа (все страны)** | 49 | **20,471** | 128,170 | 53,094 | **181,264** | **561,872,486** |
| 🇺🇸 **США (United States)** | 1 | **18,587** | 251,445 | 69,332 | **320,777** | **1,352,535,864** |
| **ИТОГО** | **51** | **40,650** | **385,484** | **123,395** | **508,879** | **1,922,666,651** |

---

## 📁 Содержимое репозитория / рабочей директории

| Файл | Описание |
| :--- | :--- |
| **`isp_cidr.db`** | Основная база данных SQLite (82 МБ) с таблицами, индексами, представлениями и оптимизацией для быстрого поиска IP. |
| **`isp_tool.py`** | Утилита командной строки и Python-библиотека для поиска по IP/ASN, фильтрации и экспорта правил. |
| **`web_server.py`** | Веб-сервер и интерактивный веб-дашборд с поиском, аналитикой и экспортом на порту `8000`. |
| **`isp_cidr_ukraine.csv`** | Полный CSV-экспорт всех CIDR подсетей и провайдеров Украины (6,838 записей). |
| **`isp_top_providers.csv`** | Топ-500 провайдеров Украины, США и Европы по объему IP-адресов. |
| **`export_ukraine_cidrs_ipv4.txt`** | Чистый текстовый список всех IPv4 CIDR Украины (построчно). |
| **`export_ukraine_cidrs_ipv6.txt`** | Чистый текстовый список всех IPv6 CIDR Украины. |
| **`export_ukraine_mikrotik.rsc`** | Скрипт импорта адресных листов для маршрутизаторов MikroTik RouterOS (`/ip firewall address-list`). |
| **`export_ukraine_ipset.sh`** | Готовый скрипт для Linux `ipset` для высокопроизводительной фильтрации. |
| **`export_ukraine_nginx.conf`** | Конфигурационный блок `geo` для веб-сервера Nginx (геоблокировка / геомаршрутизация). |

---

## 🏛 Структура базы данных (`isp_cidr.db`)

### 1. Таблица `cidr_blocks` (Основная таблица подсетей)
| Колонка | Тип | Описание |
| :--- | :--- | :--- |
| `id` | INTEGER PRIMARY KEY | Уникальный идентификатор записи |
| `cidr` | TEXT | CIDR-нотация подсети (например, `5.248.0.0/16`, `2001:678:c8::/48`) |
| `ip_version` | INTEGER | Версия IP протокола (`4` или `6`) |
| `asn` | INTEGER | Номер автономной системы (ASN) |
| `country_code` | TEXT | 2-буквенный ISO код страны (`UA`, `US`, `DE`, `FR`...) |
| `start_ip` | TEXT | Первый IP-адрес подсети (Network IP) |
| `end_ip` | TEXT | Последний IP-адрес подсети (Broadcast IP) |
| `start_ip_int` | INTEGER | Целочисленное значение начального IPv4 (для сверхбыстрого бинарного поиска) |
| `end_ip_int` | INTEGER | Целочисленное значение конечного IPv4 |
| `ip_count` | INTEGER | Количество IPv4 адресов в блоке |

**Индексы:** `idx_cidr_cidr`, `idx_cidr_asn`, `idx_cidr_cc`, `idx_cidr_range (start_ip_int, end_ip_int)`, `idx_cidr_version`.

---

### 2. Таблица `providers` (Автономные системы и провайдеры)
| Колонка | Тип | Описание |
| :--- | :--- | :--- |
| `asn` | INTEGER PRIMARY KEY | Номер автономной системы |
| `as_name` | TEXT | Краткий хэндл AS (например, `KSNET-AS`) |
| `org_name` | TEXT | Полное наименование организации / провайдера (например, `KSNET-AS "Kyivstar" PJSC`) |
| `country_code` | TEXT | ISO код страны регистрации |
| `country_name_en` | TEXT | Название страны на английском |
| `country_name_ru` | TEXT | Название страны на русском |
| `region` | TEXT | Регион (`Ukraine`, `United States`, `Europe`) |
| `ipv4_cidr_count` | INTEGER | Число IPv4 CIDR блоков |
| `ipv6_cidr_count` | INTEGER | Число IPv6 CIDR блоков |
| `total_ipv4_ips` | INTEGER | Суммарное число IPv4 адресов |

---

### 3. Таблица `countries` и `regions` (Агрегированная статистика)
Хранят предварительно рассчитанную статистику по странам и регионам для мгновенной генерации отчетов.

### 4. Представление `v_cidr_details` (View для удобных запросов)
Объединяет `cidr_blocks` с `providers` и `countries`, предоставляя единый плоский интерфейс со всеми именами и метаданными.

---

## 🏆 Крупнейшие провайдеры по регионам

### 🇺🇦 Украина (Топ-10 провайдеров)
1. **Kyivstar PJSC** (`AS15895`) — 44 CIDR, **940,800** IPv4
2. **Ukrtelecom JSC** (`AS6849`) — 219 CIDR, **605,184** IPv4
3. **VF Ukraine (Vodafone)** (`AS21497`) — 66 CIDR, **548,608** IPv4
4. **lifecell LLC** (`AS34058`) — 15 CIDR, **418,816** IPv4
5. **Triolan CDN Ltd** (`AS13188`) — 27 CIDR, **410,880** IPv4
6. **XServerCloud** (`AS202656`) — 537 CIDR, **205,824** IPv4
7. **Lanet Network Ltd** (`AS39608`) — 14 CIDR, **203,776** IPv4
8. **Farlep-Telecom (Vega)** (`AS6703`) — 108 CIDR, **149,248** IPv4
9. **MAXNET Telecom** (`AS34700`) — 27 CIDR, **122,624** IPv4
10. **TENET SPE LLC** (`AS6876`) — 16 CIDR, **114,688** IPv4

### 🇪🇺 Европа (Топ провайдеров)
1. **Deutsche Telekom AG** (`AS3320`, Германия) — 809 CIDR, **34,154,240** IPv4
2. **France Telecom / Orange** (`AS3215`, Франция) — 603 CIDR, **20,146,688** IPv4
3. **Telecom Italia S.p.A.** (`AS3269`, Италия) — 400 CIDR, **20,090,368** IPv4
4. **Mercedes-Benz Group** (`AS31399`, Германия) — 10 CIDR, **16,805,888** IPv4
5. **SFR / LDCOM** (`AS15557`, Франция) — 184 CIDR, **15,810,816** IPv4
6. **British Telecommunications (BT)** (`AS2856`, Великобритания) — 506 CIDR, **13,809,664** IPv4
7. **Vodafone DE** (`AS3209`, Германия) — 197 CIDR, **12,766,208** IPv4
8. **Telefonica de Espana** (`AS3352`, Испания) — 399 CIDR, **10,382,592** IPv4
9. **OVH SAS** (`AS16276`, Франция) — 1,930 CIDR, **4,194,304** IPv4
10. **Hetzner Online GmbH** (`AS24940`, Германия) — 386 CIDR, **3,670,016** IPv4

### 🇺🇸 США (Топ провайдеров)
1. **Amazon AWS** (`AS16509` + `AS14618`) — **176,568,318** IPv4
2. **AT&T Enterprises** (`AS7018`) — **89,228,664** IPv4
3. **Microsoft Corp** (`AS8075`) — **80,740,352** IPv4
4. **Comcast Cable** (`AS7922`) — **42,057,472** IPv4
5. **Verizon Business / UUNET** (`AS701`) — **40,576,256** IPv4
6. **Lumen / Level 3** (`AS3356`) — **27,343,488** IPv4
7. **Cogent Communications** (`AS174`) — **24,372,351** IPv4
8. **Google LLC** (`AS15169`) — **15,728,640** IPv4

---

## 🛠 Примеры использования утилиты `isp_tool.py`

### 1. Поиск информации по любому IP адресу (IPv4 / IPv6)
```bash
python3 isp_tool.py lookup 195.138.64.1
python3 isp_tool.py lookup 5.248.10.20
python3 isp_tool.py lookup 8.8.8.8
python3 isp_tool.py lookup 2001:678:c8::1
```

### 2. Поиск интернет-провайдера по названию или номеру AS
```bash
python3 isp_tool.py search "Kyivstar"
python3 isp_tool.py search "Vodafone"
python3 isp_tool.py search "Hetzner"
python3 isp_tool.py search "AS15895"
```

### 3. Просмотр топа провайдеров страны или региона
```bash
# Топ 15 провайдеров Украины:
python3 isp_tool.py top --country UA --limit 15

# Топ 15 провайдеров Германии:
python3 isp_tool.py top --country DE --limit 15

# Топ 20 провайдеров Европы:
python3 isp_tool.py top --region Europe --limit 20
```

### 4. Экспорт CIDR подсетей в различные форматы

#### Экспорт для MikroTik RouterOS:
```bash
python3 isp_tool.py export --country UA --ipv 4 --format mikrotik --out mikrotik_ua.rsc
```

#### Экспорт для Linux `ipset`:
```bash
python3 isp_tool.py export --country UA --ipv 4 --format ipset --out ipset_ua.sh
```

#### Экспорт для Nginx `geo`:
```bash
python3 isp_tool.py export --country UA --ipv 4 --format nginx --out nginx_ua.conf
```

#### Экспорт в CSV / JSON / TXT:
```bash
python3 isp_tool.py export --asn 15895 --format csv --out kyivstar_cidrs.csv
python3 isp_tool.py export --country UA --format txt --out ukraine_cidrs.txt
```

---

## 💻 Примеры SQL-запросов к `isp_cidr.db`

### Поиск подсети по IP адресу (мгновенный поиск через целочисленный индекс):
```sql
SELECT c.cidr, c.asn, p.org_name, c.country_code, cnt.country_name_ru
FROM cidr_blocks c
LEFT JOIN providers p ON c.asn = p.asn
LEFT JOIN countries cnt ON c.country_code = cnt.country_code
WHERE c.ip_version = 4 
  AND c.start_ip_int <= 3280650241  -- int(195.138.64.1)
  AND c.end_ip_int >= 3280650241
LIMIT 1;
```

### Выборка всех подсетей конкретного провайдера (например, Киевстар):
```sql
SELECT c.cidr, c.ip_version, c.start_ip, c.end_ip, c.ip_count
FROM cidr_blocks c
WHERE c.asn = 15895
ORDER BY c.ip_version, c.start_ip_int;
```

### Статистика распределения IPv4 адресов по странам Европы:
```sql
SELECT country_code, country_name_ru, total_asns, total_cidrs, total_ipv4_ips
FROM countries
WHERE region = 'Europe'
ORDER BY total_ipv4_ips DESC;
```

---

## 🐍 Использование в Python

```python
import sqlite3
import ipaddress

conn = sqlite3.connect("isp_cidr.db")
cur = conn.cursor()

def find_isp_by_ip(ip_str):
    ip_int = int(ipaddress.IPv4Address(ip_str))
    cur.execute("""
        SELECT cidr, asn, isp_name, country_name_ru, region
        FROM v_cidr_details
        WHERE ip_version = 4 AND start_ip_int <= ? AND end_ip_int >= ?
        LIMIT 1
    """, (ip_int, ip_int))
    return cur.fetchone()

result = find_isp_by_ip("5.248.10.20")
print(result)
# ('5.248.0.0/16', 15895, 'KSNET-AS "Kyivstar" PJSC', 'Украина', 'Ukraine')
```

---

## 🌐 Веб-интерфейс и REST API

Веб-дашборд запущен локально на порту `8000`:
- **URL**: `http://localhost:8000/`
- **Доступные API методы**:
  - `GET /api/stats` — сводная статистика по регионам и странам.
  - `GET /api/lookup?ip=X.X.X.X` — проверка любого IP.
  - `GET /api/search?q=Kyivstar&country=UA&page=1` — фильтрация и пагинация подсетей.
  - `GET /api/top_providers?country=UA` — лидерборд провайдеров.
  - `GET /api/export?country=UA&format=mikrotik` — скачивание сгенерированных файлов.
