# Agent Supervisor

The supervisor monitors multi-agent execution.

Responsibilities:

- check heartbeat freshness;
- detect stalled agents;
- create recovery signals;
- update supervisor state.

Run:

```bash
python3 supervisor.py
```

State is stored in:

```
supervisor/supervisor_state.json
```
