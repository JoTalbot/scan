# Agent Lifecycle Protocol

Lifecycle states:

```
spawn -> training -> active -> upgrade -> retired
```

Rules:

- Spawn only when capability gap exists.
- Training uses verified skills.
- Active agents receive tasks through dispatcher.
- Upgrade adds new capabilities.
- Retired agents preserve reusable knowledge.

Flow:

```
Performance Data
      |
      v
Lifecycle Manager
      |
      +--> Upgrade
      |
      +--> Retire
      |
      v
Knowledge Migration
```
