# Agent Training Protocol

## Lifecycle

```
Spawned Agent
    ↓
Load Verified Skills
    ↓
Training Tasks
    ↓
Competency Evaluation
    ↓
Active Agent
```

Rules:
- new agents inherit only verified skills;
- training results update reputation;
- failed evaluation returns agent to training queue;
- successful agents are registered in capability registry.
