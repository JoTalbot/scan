# 🧠 Agent Skill: Network Firewall & Router Configuration Generator

> **Skill Slug:** `network_firewall_export_generator`  
> **Status:** Production-Ready  
> **Author:** Agent-Primary  

---

## 🎯 Назначение
Трансформация списков CIDR подсетей провайдеров и стран в нативные конфигурации сетевого оборудования (MikroTik RouterOS, Linux IPSet, NFTables, Cisco ACL, Nginx Geo).

---

## 💻 Форматы и шаблоны генерации

### 1. MikroTik RouterOS (`.rsc`)
```routeros
/ip firewall address-list
add list="ISP_UA" address=5.248.0.0/16 comment="AS15895 Kyivstar PJSC"
```

### 2. Linux IPSet (Высокопроизводительный фильтр в ядре Linux)
```bash
create isp_ua hash:net family inet hashsize 1024 maxelem 655360
add isp_ua 5.248.0.0/16
```
Применение в iptables:
```bash
iptables -A INPUT -m set --match-set isp_ua src -j ACCEPT
```

### 3. Nginx Geo Mapping (`.conf`)
```nginx
geo $is_ukraine_provider {
    default 0;
    5.248.0.0/16 1;
    195.138.64.0/19 1;
}
```

### 4. Cisco IOS Prefix-List
```cisco
ip prefix-list PL_ISP_UA seq 10 permit 5.248.0.0/16
```
