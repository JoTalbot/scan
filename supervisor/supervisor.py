#!/usr/bin/env python3
"""Agent Supervisor watchdog for nonstop multi-agent scans."""

import json
import time
from pathlib import Path

STATE = Path("supervisor/supervisor_state.json")
HEARTBEAT = Path(".agents/heartbeat.json")
TIMEOUT = 30 * 60


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def main():
    state = load_json(STATE, {"supervisor": "active", "agents": [], "alerts": []})
    heartbeat = load_json(HEARTBEAT, {})
    now = time.time()

    alerts = []
    for agent, data in heartbeat.items():
        last = data.get("timestamp", 0)
        if now - last > TIMEOUT:
            alerts.append({"agent": agent, "status": "stale", "action": "create_recovery_task"})

    state["last_check"] = int(now)
    state["alerts"] = alerts
    STATE.write_text(json.dumps(state, indent=2))

    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
