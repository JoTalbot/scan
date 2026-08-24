# 🖥️ Мультимашинное сканирование и автоцикл (pipeline)

## Контекст применения
Проект спроектирован для распределённой работы (AGENTS.md): несколько агентов на разных машинах синхронизируются через git. Данный скилл описывает, как масштабировать сканирование на N машин и автоматизировать полный цикл.

## Мультимашинный скан (шардирование)
`port_scanner.py` поддерживает шарды:
```bash
# Машина 1 из 4:
python3 port_scanner.py run --batch 1000000 --shard 0 --shard-total 4 --concurrency 500
# Машина 2 из 4:
python3 port_scanner.py run --batch 1000000 --shard 1 --shard-total 4 --concurrency 500
```
- Каждая машина берёт свой срез целей (дедупликация — через `scan_results.ip_int` в БД, затем синк через git).
- Перед запуском на каждой машине: `git pull --rebase origin main`.
- После скана: `python3 sync_manager.py "<AGENT>"` — пуш чанков и БД.

## Автоцикл (pipeline.sh)
```bash
./pipeline.sh 100000    # скан 100k + аудит + probe + sync
```
Этапы: git pull → lock → скан → подсчёт новых → raw-аудит (--fast) → browser-аудит (fast) → уведомление о находках (Telegram, если настроен в .env: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID) → complete → sync_manager → push.

⚠️ **SSH/Telnet-аудит и Port probe+SNMP в автоцикле ОТКЛЮЧЕНЫ** (по запросу владельца). Соответствующие блоки в pipeline.sh закомментированы с пометкой «ОТКЛЮЧЕНО» — при необходимости раскомментировать. Инструменты `router_ssh_telnet_audit.py` и `port_probe.py` при этом остаются доступны для ручного запуска.

Пример cron (каждые 6 часов):
```
0 */6 * * * /root/scan/pipeline.sh 100000 >> /root/scan/logs/cron.log 2>&1
```

## port_probe.py — доп. порты и SNMP
```bash
python3 port_probe.py                          # все роутеры: TCP 8291/8728/7547/8080/8443/23/22 + SNMP public/private
python3 port_probe.py --targets ip1,ip2        # точечно
python3 port_probe.py --snmp-only              # только SNMP
```
- Результаты: `scan_routers.extra_ports` (JSON), таблицы `device_ports` и `snmp_results`.
- SNMP реализован raw (без библиотек): SNMPv1 GET sysDescr.
- **Важно:** SNMP-ответы (community public/private) могут раскрыть модель/конфиг — проверять в первую очередь.

## verify_findings.py — double-check находок
```bash
python3 verify_findings.py --hours 12   # перепроверка пар старше 12ч
python3 verify_findings.py --ip X.X.X.X
```
- Динамические IP меняют содержимое — находка может исчезнуть.
- Подтверждённые пары обновляют checked_at; исчезнувшие помечаются +revoked.

## Приоритизация целей (плотность роутеров)
```bash
# Только residential-провайдеры (cable/dsl/fiber/telecom в названии):
python3 port_scanner.py run --batch 100000 --isp-words "cable,dsl,fiber,telecom,communications"
```

## Типичные ошибки
- Перед запуском всегда `git pull --rebase` — БД могла измениться другим агентом.
- `pkill` с паттерном из собственной командной строки убивает сам bash — использовать python-скрипт по /proc (см. опыт).
- SNMP UDP может не отвечать на некоторых VPS (блокировка ICMP/UDP) — это нормально.
- MikroTik API (8728): challenge привязан к соединению — login и response строго в одной сессии (иначе ложные срабатывания).

## Критерии верификации
- `device_ports` содержит открытые доп. порты; `scan_routers.extra_ports` заполнен.
- `snmp_results` непуст при наличии SNMP-устройств.
- pipeline.sh проходит полный цикл за время ≤ скан + 30 мин.
