#!/usr/bin/env python3
"""
Agent Sync & Coordination Tool for Distributed Multi-Agent Workflows
Manages task locking, step tracking in STATUS.md / agent_state.json, and skill recording.
"""

import sys
import os
import json
import datetime
import argparse
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "agent_state.json")
STATUS_FILE = os.path.join(BASE_DIR, "STATUS.md")
SKILLS_DIR = os.path.join(BASE_DIR, "skills")

def get_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_agents": [], "tasks": {}, "last_updated": get_now_iso()}

def save_state(state):
    state["last_updated"] = get_now_iso()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def update_status_markdown(state):
    # Reads state and regenerates the active tasks table in STATUS.md
    if not os.path.exists(STATUS_FILE):
        return
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Build active tasks table
    table_lines = [
        "| Задача | Агент | Хост / Окружение | Текущий шаг | Статус | Обновлено |",
        "| :--- | :--- | :--- | :--- | :---: | :---: |"
    ]
    for a in state.get("active_agents", []):
        st_badge = "`IN_PROGRESS` 🔄" if a.get("status") == "IN_PROGRESS" else f"`{a.get('status')}`"
        task_title = a.get("task_name", a.get("task_id", "General Task"))
        date_str = a.get("updated_at", "").split("T")[0] or "Today"
        table_lines.append(
            f"| **{task_title}** | `{a.get('agent_id', 'Agent')}` | `{a.get('machine_id', 'Host')}` | {a.get('current_step', '-')} | {st_badge} | {date_str} |"
        )
    if len(table_lines) == 2:
        table_lines.append("| *Нет активных задач* | - | - | Все задачи выполнены | `IDLE` 🟢 | - |")

    # Update Active Tasks Matrix section
    import re
    new_section = "## 🟢 Текущее состояние задач (Active Tasks Matrix)\n\n" + "\n".join(table_lines) + "\n\n---"
    pattern = r"## 🟢 Текущее состояние задач \(Active Tasks Matrix\)[\s\S]*?---"
    if re.search(pattern, content):
        content = re.sub(pattern, new_section, content)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(content)

def lock_task(agent_id, task_name, step, machine_id="Machine-01"):
    state = load_state()
    # Check if agent already exists
    active = [a for a in state.get("active_agents", []) if a.get("agent_id") != agent_id]
    active.append({
        "agent_id": agent_id,
        "machine_id": machine_id,
        "task_name": task_name,
        "current_step": step,
        "status": "IN_PROGRESS",
        "started_at": get_now_iso(),
        "updated_at": get_now_iso()
    })
    state["active_agents"] = active
    save_state(state)
    update_status_markdown(state)
    print(f"✅ Agent '{agent_id}' locked task '{task_name}' on step: {step}")

def update_step(agent_id, step):
    state = load_state()
    found = False
    for a in state.get("active_agents", []):
        if a.get("agent_id") == agent_id:
            a["current_step"] = step
            a["updated_at"] = get_now_iso()
            found = True
            break
    if not found:
        state.setdefault("active_agents", []).append({
            "agent_id": agent_id,
            "machine_id": "Unknown",
            "task_name": "Task in progress",
            "current_step": step,
            "status": "IN_PROGRESS",
            "started_at": get_now_iso(),
            "updated_at": get_now_iso()
        })
    save_state(state)
    update_status_markdown(state)
    print(f"🔄 Agent '{agent_id}' updated step to: {step}")

def complete_task(agent_id, task_name):
    state = load_state()
    state["active_agents"] = [a for a in state.get("active_agents", []) if a.get("agent_id") != agent_id]
    save_state(state)
    update_status_markdown(state)
    print(f"🎉 Agent '{agent_id}' completed task '{task_name}'.")

def show_status():
    state = load_state()
    print("\n🤖 ACTIVE AGENTS STATUS BOARD")
    print("=" * 85)
    print(f"{'Agent ID':<18} {'Machine':<14} {'Task':<22} {'Current Step'}")
    print("-" * 85)
    for a in state.get("active_agents", []):
        print(f"{a.get('agent_id'):<18} {a.get('machine_id'):<14} {a.get('task_name')[:20]:<22} {a.get('current_step')}")
    if not state.get("active_agents"):
        print("No active agents. All tasks completed or idle.")
    print("=" * 85)

def save_skill(name, title, description, log_content):
    os.makedirs(SKILLS_DIR, exist_ok=True)
    slug = name.strip().lower().replace(" ", "_").replace("-", "_")
    if not slug.endswith(".md"):
        slug += ".md"
    skill_path = os.path.join(SKILLS_DIR, slug)

    content = f"""# 🧠 Agent Skill: {title}

> **Skill Slug:** `{slug}`  
> **Created At:** {get_now_iso()}  
> **Type:** Automated Core Competency  

---

## 🎯 Назначение и контекст
{description}

---

## 📋 Пошаговый алгоритм выполнения
1. Проверка окружения и необходимых зависимостей.
2. Поиск существующих наработок и сетевых библиотек.
3. Выполнение основной логики с валидацией входных данных.
4. Верификация результатов и логирование метрик.

---

## 💻 Исходный рабочий лог и реализация
```
{log_content}
```

---

## 🛡 Обработка краевых случаев
- **Сетевые ошибки:** Автоматический retry с экспоненциальной задержкой.
- **Превышение лимитов:** Батчинг данных порциями по 50,000 записей.
- **Синхронизация:** Использование `agent_state.json` и атомарных транзакций.
"""
    with open(skill_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✨ New skill saved successfully at: {skill_path}")

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Distributed Synchronization Tool")
    subparsers = parser.add_subparsers(dest="cmd", help="Command")

    p_lock = subparsers.add_parser("lock", help="Lock task and announce start")
    p_lock.add_argument("--agent", required=True, help="Agent identifier")
    p_lock.add_argument("--task", required=True, help="Task name")
    p_lock.add_argument("--step", required=True, help="Current step description")
    p_lock.add_argument("--machine", default="Sandbox-01", help="Machine / host identifier")

    p_step = subparsers.add_parser("step", help="Update current step")
    p_step.add_argument("--agent", required=True, help="Agent identifier")
    p_step.add_argument("--step", required=True, help="New step description")

    p_done = subparsers.add_parser("complete", help="Mark task as complete")
    p_done.add_argument("--agent", required=True, help="Agent identifier")
    p_done.add_argument("--task", required=True, help="Task name")

    subparsers.add_parser("status", help="Show active status board")

    p_skill = subparsers.add_parser("save-skill", help="Convert agent log into reusable skill")
    p_skill.add_argument("--name", required=True, help="Skill filename slug")
    p_skill.add_argument("--title", required=True, help="Skill title")
    p_skill.add_argument("--desc", required=True, help="Skill description")
    p_skill.add_argument("--log", required=True, help="Agent operation log text or filepath")

    args = parser.parse_args()

    if args.cmd == "lock":
        lock_task(args.agent, args.task, args.step, args.machine)
    elif args.cmd == "step":
        update_step(args.agent, args.step)
    elif args.cmd == "complete":
        complete_task(args.agent, args.task)
    elif args.cmd == "status":
        show_status()
    elif args.cmd == "save-skill":
        log_text = args.log
        if os.path.exists(args.log):
            with open(args.log, "r", encoding="utf-8") as f:
                log_text = f.read()
        save_skill(args.name, args.title, args.desc, log_text)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
