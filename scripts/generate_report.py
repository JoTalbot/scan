#!/usr/bin/env python3
"""
Ежедневный отчёт по проекту (для GitHub Actions).
Читает isp_cidr.db (предварительно распакованную из isp_cidr.db.gz),
формирует REPORT.md со статистикой сканирования, роутеров и аудита.

Usage:
    python3 scripts/generate_report.py [путь_к_базе]   (по умолчанию isp_cidr.db)
"""
import os
import sys
import sqlite3
import datetime

DB = sys.argv[1] if len(sys.argv) > 1 else "isp_cidr.db"


def q(cur, sql):
    try:
        return cur.execute(sql).fetchone()[0]
    except Exception:
        return 0


def main():
    if not os.path.exists(DB):
        print("Нет базы данных:", DB)
        sys.exit(1)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    scanned = q(cur, "SELECT COUNT(*) FROM scan_results")
    banners = q(cur, "SELECT COUNT(*) FROM scan_results WHERE has_banner = 1")
    routers = q(cur, "SELECT COUNT(*) FROM scan_routers")
    creds = q(cur, "SELECT COUNT(*) FROM router_credentials")
    raw_checked = q(cur, "SELECT COUNT(*) FROM scan_routers WHERE auth_checked = 1")
    br_checked = q(cur, "SELECT COUNT(*) FROM scan_routers WHERE browser_checked = 1")

    lines = []
    lines.append("# 📊 Ежедневный отчёт — RouterScan Project\n")
    lines.append(f"**Сформирован:** {now}\n")
    lines.append("## 📈 Общая статистика\n")
    lines.append("| Метрика | Значение |")
    lines.append("| :--- | :---: |")
    lines.append(f"| Просканировано IP | {scanned:,} |")
    lines.append(f"| Веб-баннеров | {banners:,} |")
    lines.append(f"| Роутеров обнаружено | {routers:,} |")
    lines.append(f"| Проверено raw-каналами | {raw_checked:,} |")
    lines.append(f"| Проверено браузером | {br_checked:,} |")
    lines.append(f"| Найдено пар | {creds:,} |")
    lines.append("")

    # роутеры по вендорам
    lines.append("## 🛜 Роутеры по вендорам\n")
    lines.append("| Вендор | Кол-во |")
    lines.append("| :--- | :---: |")
    for v, c in cur.execute("SELECT vendor, COUNT(*) c FROM scan_routers GROUP BY vendor ORDER BY c DESC LIMIT 15"):
        lines.append(f"| {v or 'Unknown'} | {c} |")
    lines.append("")

    # статусы аудита
    lines.append("## 🔍 Статусы аудита (raw)\n")
    lines.append("| Статус | Кол-во |")
    lines.append("| :--- | :---: |")
    for s, c in cur.execute("SELECT COALESCE(auth_result, 'not-checked') s, COUNT(*) c FROM scan_routers GROUP BY s ORDER BY c DESC"):
        lines.append(f"| {s} | {c} |")
    lines.append("")

    # найденные пары
    lines.append("## 🔑 Найденные пары\n")
    try:
        rows = cur.execute("SELECT ip, vendor, username, password, auth_method, checked_at "
                           "FROM router_credentials ORDER BY id DESC LIMIT 50").fetchall()
    except Exception:
        rows = []
    if rows:
        lines.append("| IP | Вендор | Логин | Пароль | Метод | Дата |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for ip, v, u, p, m, d in rows:
            lines.append(f"| {ip} | {v or '-'} | {u} | {p or '(пусто)'} | {m} | {d or '-'} |")
    else:
        lines.append("_Пар не найдено._")
    lines.append("")

    # топ серверов
    lines.append("## 🌐 Топ Web-серверов\n")
    lines.append("| Server | Кол-во |")
    lines.append("| :--- | :---: |")
    for s, c in cur.execute("SELECT COALESCE(NULLIF(server_header,''), '(hidden)') s, COUNT(*) c "
                            "FROM scan_results WHERE has_banner=1 GROUP BY s ORDER BY c DESC LIMIT 10"):
        lines.append(f"| {s[:60]} | {c} |")
    lines.append("")
    lines.append("---\n*Авто-отчёт, генерируется GitHub Actions ежедневно.*")

    conn.close()

    with open("REPORT.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("REPORT.md создан:", len(lines), "строк")


if __name__ == "__main__":
    main()
