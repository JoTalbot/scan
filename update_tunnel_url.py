#!/usr/bin/env python3
"""
Обновление URL Cloudflare Tunnel в GitHub Pages
================================================
Следит за logs/cloudflared.log, извлекает актуальный trycloudflare URL
и обновляет site_control/index.html (кнопки Старт/Стоп на GitHub Pages).
При изменении — коммит + push (Pages пересоберётся автоматически).

Usage:
    python3 update_tunnel_url.py          # проверить и обновить
    python3 update_tunnel_url.py --cron   # режим cron (без вывода)
"""
import os
import re
import sys
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
TUNNEL_LOG = os.path.join(BASE, "logs", "cloudflared.log")
INDEX = os.path.join(BASE, "site_control", "index.html")


def get_tunnel_url():
    """URL из лога или journald (systemd-сервис пишет туда)."""
    # 1. из файла (nohup-режим)
    if os.path.exists(TUNNEL_LOG):
        with open(TUNNEL_LOG, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", content)
        if m:
            return m.group(0)
    # 2. из journald (systemd-режим)
    try:
        r = subprocess.run(
            ["journalctl", "-u", "cloudflared-tunnel", "--no-pager", "-n", "100"],
            capture_output=True, text=True, timeout=15)
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", r.stdout or "")
        if m:
            return m.group(0)
    except Exception:
        pass
    return None


def update():
    url = get_tunnel_url()
    if not url:
        print("Туннель-URL не найден в логе")
        return False
    if not os.path.exists(INDEX):
        print("index.html не найден")
        return False

    with open(INDEX, encoding="utf-8") as f:
        content = f.read()

    old = re.search(r'const TUNNEL = "[^"]*";', content)
    old_url = old.group(0) if old else None
    new_line = f'const TUNNEL = "{url}";'

    if old_url == new_line:
        print(f"URL актуален: {url}")
        return False

    content = re.sub(r'const TUNNEL = "[^"]*";', new_line, content)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"URL обновлён: {url}")

    # коммит + push
    os.chdir(BASE)
    subprocess.run(["git", "add", "site_control/index.html"], check=False)
    r = subprocess.run(["git", "commit", "-m", f"chore: tunnel url {url}"],
                       capture_output=True, text=True, check=False)
    if r.returncode == 0:
        subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, check=False)
        print("Запушено на GitHub (Pages обновится)")
    else:
        print("Коммит не создан (нет изменений?)")
    return True


if __name__ == "__main__":
    if "--cron" in sys.argv:
        update()
    else:
        update()
