# Agent Supervisor Protocol

## Purpose
Central controller for autonomous multi-agent coordination.

## Responsibilities

- Monitor agent heartbeats.
- Detect stalled agents.
- Validate task ownership.
- Detect conflicting changes.
- Create recovery tasks.
- Maintain system stability.

## Supervisor Loop

1. Read `.agents/HEARTBEAT.md`.
2. Read `.agents/TASK_QUEUE.md`.
3. Check active agents.
4. Detect timeout or conflict.
5. Assign corrective action.
6. Write supervisor report.

## Rules

Every agent must:
- update heartbeat before and after work;
- never silently abandon a task;
- record blockers;
- preserve shared state.
