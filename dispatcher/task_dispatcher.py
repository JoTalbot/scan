import json
from pathlib import Path

ROOT = Path(__file__).parent.parent

AGENTS = ROOT / "supervisor" / "agents.json"
QUEUE = ROOT / ".agents" / "TASK_QUEUE.md"


def load_agents():
    if not AGENTS.exists():
        return []
    return json.loads(AGENTS.read_text()).get("agents", [])


def dispatch(task):
    agents = load_agents()
    required = task.get("capability")
    candidates = [a for a in agents if required in a.get("capabilities", [])]
    if not candidates:
        return {"status": "queued", "reason": "no capable agent"}
    selected = candidates[0]
    return {
        "status": "assigned",
        "agent": selected.get("id"),
        "task": task.get("id")
    }


if __name__ == "__main__":
    print(dispatch({"id": "scan", "capability": "code_scan"}))
