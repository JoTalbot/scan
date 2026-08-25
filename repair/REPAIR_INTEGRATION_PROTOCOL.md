# Repair Integration Protocol

## Purpose

Connect Repair Agent with Orchestrator, Task Queue and Verification.

## Flow

```
Scan Detection
    ↓
Create Repair Task
    ↓
Dispatcher Assignment
    ↓
Repair Agent
    ↓
Regression Verification
    ↓
Memory Update
```

## Rules

- Every repair must have a verification step.
- Failed repairs return to the task queue.
- Successful repairs create reusable knowledge.
- Repeated failures increase task priority.
