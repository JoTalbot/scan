#!/usr/bin/env python3
"""
OpenHands Cloud Agent (исполнитель для умных задач)
====================================================
Отправляет задачу агенту OpenHands Cloud, который работает в репозитории
JoTalbot/scan (клонирует, анализирует, пишет код, создаёт PR/коммиты).

Отличие от других исполнителей (circleci/e2b/local): это ИИ-агент — он
сам решает КАК выполнить задачу. Подходит для:
  * анализа данных и добавления сигнатур в router_detect.py
  * обновления отчётов/README/документации
  * рефакторинга и исправления багов в коде
  * генерации тестов

API: https://app.all-hands.dev/api/v1/app-conversations
Ключ: OPENHANDS_API_KEY (sk-oh-...) в .env

Usage:
    python3 openhands_agent.py --task "Добавь сигнатуры для новых роутеров"
    python3 openhands_agent.py --task "..." --wait 600 --repo JoTalbot/scan
    python3 openhands_agent.py --status <conversation_id>
"""

import os
import sys
import time
import json
import argparse
import datetime
import urllib.request

BASE = "https://app.all-hands.dev/api/v1/app-conversations"


def get_key():
    k = os.environ.get("OPENHANDS_API_KEY", "")
    if not k and os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("OPENHANDS_API_KEY="):
                k = line.split("=", 1)[1].strip()
    return k


def api(method, path, data=None, timeout=60):
    key = get_key()
    req = urllib.request.Request(BASE + path, method=method,
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    if data is not None:
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}


def start_task(task, repo, branch=None):
    payload = {
        "initial_message": {"run": True,
                            "content": [{"type": "text", "text": task}]},
        "selected_repository": repo,
    }
    if branch:
        payload["selected_branch"] = branch
    return api("POST", "", payload)


def get_status(cid):
    """Статус по id: POST возвращает start-task id, реальный conversation ищем в search."""
    d = api("GET", f"/search?ids={cid}")
    if isinstance(d, list) and d and isinstance(d[0], dict):
        return d[0]
    # fallback: ищем по id в списке свежих
    d2 = api("GET", "/search?limit=20")
    items = d2.get("items", d2) if isinstance(d2, dict) else d2
    if isinstance(items, list):
        for x in items:
            if isinstance(x, dict) and x.get("id") == cid:
                return x
            # start-task id может отличаться; ищем по времени создания
            if isinstance(x, dict) and x.get("id", "").startswith(cid[:12]):
                return x
    return None


def find_recent(start_iso, limit=20):
    """Ищем самый свежий разговор после start_iso (по created_at)."""
    try:
        d = api("GET", f"/search?created_at__gte={start_iso}&limit={limit}")
    except Exception:
        d = None
    items = d.get("items", d) if isinstance(d, dict) else d
    if isinstance(items, list):
        cands = [x for x in items if isinstance(x, dict) and x.get("created_at", "") >= start_iso]
        if cands:
            cands.sort(key=lambda x: x.get("created_at", ""))
            return cands[-1]
    return None


def main():
    parser = argparse.ArgumentParser(description="OpenHands Cloud agent")
    parser.add_argument("--task", help="Задача для агента")
    parser.add_argument("--repo", default="JoTalbot/scan")
    parser.add_argument("--branch", default=None)
    parser.add_argument("--wait", type=int, default=1200, help="Макс. ожидание (сек)")
    parser.add_argument("--poll", type=int, default=20, help="Интервал опроса (сек)")
    parser.add_argument("--status", help="Показать статус разговора по id")
    parser.add_argument("--diff", help="Показать git diff разговора по id")
    args = parser.parse_args()

    if not get_key():
        print("❌ Нет OPENHANDS_API_KEY (sk-oh-...) в .env")
        sys.exit(1)

    if args.status:
        d = get_status(args.status)
        if d:
            print(f"id: {d.get('id')}")
            print(f"execution: {d.get('execution_status')} | sandbox: {d.get('sandbox_status')}")
            print(f"url: {d.get('conversation_url')}")
            print(f"metrics: {json.dumps(d.get('metrics', {}), ensure_ascii=False)[:200]}")
        else:
            print("Не найден")
        return

    if args.diff:
        d = api("GET", f"/{args.diff}/git/diff?path=/")
        print(json.dumps(d, ensure_ascii=False)[:2000])
        return

    if not args.task:
        parser.print_help()
        return

    print(f"🚀 Отправляю задачу OpenHands (repo={args.repo}):")
    print(f"   {args.task}")
    d = start_task(args.task, args.repo, args.branch)
    if d.get("error"):
        print(f"❌ Ошибка: {d}")
        sys.exit(1)

    cid = d.get("id")
    start_iso = (datetime.datetime.now(datetime.timezone.utc) -
                 datetime.timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n📋 start-task id: {cid}")
    print(f"🔗 https://app.all-hands.dev/conversations/{cid}")
    print(f"   статус при создании: {d.get('status')}\n")

    # поллинг до завершения (ищем реальный conversation по времени)
    t0 = time.time()
    last_title = None
    while time.time() - t0 < args.wait:
        time.sleep(args.poll)
        st = find_recent(start_iso)
        if not st:
            print(f"   [{int(time.time()-t0)}s] разговор ещё не создан...", flush=True)
            continue
        real_id = st.get("id")
        exec_st = st.get("execution_status")
        sand_st = st.get("sandbox_status")
        title = st.get("title") or ""
        if title != last_title:
            print('   [%ds] conversation=%s title=%s' % (int(time.time()-t0), real_id[:16], title[:50]))
            last_title = title
        if exec_st in ("running", None) or sand_st == "RUNNING":
            continue
        if exec_st in ("error", "failed", "canceled"):
            print(f"⚠️ Завершился со статусом {exec_st}")
        else:
            print("✅ Задача выполнена!")
        print(f"   url: {st.get('conversation_url')}")
        print(f"   metrics: {json.dumps(st.get('metrics', {}), ensure_ascii=False)[:300]}")
        # события/вывод агента (последние сообщения через runtime URL)
        try:
            run_url = (st.get("conversation_url") or "").replace("/api/conversations/", "/api/conversations/")
            if run_url and st.get("session_api_key"):
                req = urllib.request.Request(run_url + "/events?limit=30",
                                             headers={"Authorization": f"Bearer {st['session_api_key']}"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    evs = json.loads(resp.read().decode())
                msgs = []
                for e in evs if isinstance(evs, list) else []:
                    if isinstance(e, dict) and e.get("type") == "message" and e.get("message"):
                        role = e["message"].get("role", "?")
                        c = e["message"].get("content")
                        if isinstance(c, list):
                            txt = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                        else:
                            txt = str(c or "")
                        if txt.strip() and role in ("assistant", "user"):
                            msgs.append(f"[{role}] {txt[:400]}")
                if msgs:
                    print("\n=== ПОСЛЕДНИЕ СООБЩЕНИЯ АГЕНТА ===")
                    print("\n".join(msgs[-6:]))
        except Exception as ex:
            print(f"\n(не удалось получить события: {ex})")
        # git diff изменений
        try:
            diff = api("GET", f"/{real_id}/git/diff?path=/", timeout=30)
            if isinstance(diff, dict) and "error" not in diff:
                s = json.dumps(diff, ensure_ascii=False)
                print(f"\n=== GIT DIFF ({len(s)} симв.) ===")
                print(s[:2500])
        except Exception:
            pass
        return
    print("⏰ Таймаут ожидания. Проверьте: https://app.all-hands.dev/conversations/" + cid)


if __name__ == "__main__":
    main()
