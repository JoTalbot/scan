# Agent Capability Marketplace Protocol

## Purpose

Shared registry for agent skills and capabilities.

## Flow

```
Agent Capability
      |
      v
Publish Skill
      |
      v
Registry
      |
      v
Capability Match
      |
      v
Task Assignment
```

## Rules

- Agents publish verified capabilities.
- Capabilities include confidence score.
- Dispatcher selects the best matching agent.
- Successful executions update reputation.
