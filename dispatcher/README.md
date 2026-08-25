# Task Dispatcher 2.0

Capability-based routing layer for multi-agent execution.

Flow:

```
Task Queue
    |
    v
Dispatcher
    |
    +--> capability match
    |
    +--> assign agent
    |
    v
Agent execution
```

Features:
- agent capability matching;
- task routing;
- future priority scoring;
- conflict lock integration.
