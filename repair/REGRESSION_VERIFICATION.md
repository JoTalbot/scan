# Regression Verification Protocol

## Purpose

Ensure every automatic repair does not introduce new failures.

## Flow

```
Detect issue
  ↓
Repair Agent
  ↓
Run verification
  ↓
Compare baseline
  ↓
Store result
```

## Rules

- Every fix requires verification.
- Failed verification returns task to queue.
- Successful repairs become reusable skills.
- Results are stored in memory.
