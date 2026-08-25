# Agent Post Task Protocol

After completing work every AI agent must:

1. Update heartbeat.
2. Record result in logs.
3. Extract reusable knowledge.
4. Create or update a skill if a reusable solution was found.
5. Update `skills/index.json`.
6. Mark task completion in `TASK_QUEUE.md`.

Knowledge is part of the project and must survive agent replacement.
