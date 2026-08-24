# 🧠 Agent Skill: ISP CIDR Discovery, Processing & High-Performance Indexing

> **Skill Slug:** `isp_cidr_discovery_and_indexing`  
> **Status:** Production-Ready  
> **Author:** Agent-Primary  

---

## 🎯 Назначение
Навык автоматического сбора, нормализации, сжатия префиксов и высокопроизводительной индексации глобальных адресных пространств интернет-провайдеров (Украина, США, Европа).

---

## 📋 Предварительные требования и источники данных
1. **RIPE NCC ASN Directory:** `https://ftp.ripe.net/ripe/asnames/asn.txt` (122,000+ записей официальных владельцев AS).
2. **IP to ASN Combined Feed:** `https://iptoasn.com/data/ip2asn-combined.tsv.gz` (715,000+ диапазонов IPv4 & IPv6).
3. **RIR Delegations:** `https://ftp.ripe.net/ripe/stats/delegated-ripencc-latest` и `https://ftp.arin.net/pub/stats/arin/delegated-arin-extended-latest`.

---

## ⚙️ Алгоритм реализации

### Шаг 1: Конвертация диапазонов IP в минимальный набор CIDR
Для преобразования любого произвольного диапазона `(start_ip, end_ip)` в канонические CIDR подсети используется алгоритм агрегации:

```python
import ipaddress

def range_to_cidrs(start_ip_str, end_ip_str):
    s = ipaddress.ip_address(start_ip_str)
    e = ipaddress.ip_address(end_ip_str)
    return list(ipaddress.summarize_address_range(s, e))
```

### Шаг 2: Целочисленные индексы для бинарного поиска подсети за < 1 мс
Хранение IPv4 адресов в виде `INTEGER` (`uint32`) в SQLite позволяет находить подсеть любого входящего IP через стандартный B-Tree индекс:

```sql
CREATE INDEX idx_cidr_range ON cidr_blocks(start_ip_int, end_ip_int);

-- Поиск подсети для IP (например, 195.138.64.1 -> 3280650241):
SELECT * FROM cidr_blocks 
WHERE ip_version = 4 
  AND start_ip_int <= 3280650241 
  AND end_ip_int >= 3280650241
LIMIT 1;
```

### Шаг 3: Массовая вставка (Batching)
Использование транзакций пакетами по 50,000 записей и `PRAGMA synchronous = OFF` обеспечивает скорость вставки свыше **50,000 строк в секунду**.
