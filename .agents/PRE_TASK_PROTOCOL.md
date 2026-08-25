# Agent Pre Task Protocol

Before starting work every AI agent must:

1. Read `.agents/HEARTBEAT.md`.
2. Read `.agents/TASK_QUEUE.md`.
3. Read relevant skills from `skills/`.
4. Check `skills/index.json`.
5. Claim a task in the queue.
6. Write heartbeat status.

No agent should repeat work already completed by another agent without verification.
