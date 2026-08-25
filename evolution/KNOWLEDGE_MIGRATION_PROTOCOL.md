# Knowledge Migration Protocol

## Purpose

Preserve useful agent knowledge during lifecycle transitions.

## Flow

```text
Retire Agent
    ↓
Extract Skills
    ↓
Validate Knowledge
    ↓
Merge Duplicates
    ↓
Publish To Memory
    ↓
Available To Active Agents
```

Rules:

- Never delete verified skills with active usage.
- Keep provenance of migrated knowledge.
- Prefer verified and higher-confidence skills.
- Update capability registry after migration.
