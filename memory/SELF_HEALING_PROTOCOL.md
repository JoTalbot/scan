# Self Healing Protocol

## Goal

Automatic recovery loop for detected problems.

## Flow

```
Detect
  ↓
Analyze
  ↓
Find Memory Context
  ↓
Apply Fix
  ↓
Verify
  ↓
Store New Skill
```

## Rules

- Every fix must be verified.
- Failed fixes create recovery tasks.
- Successful fixes update memory and skills.
- Agents must record lessons learned.

## Knowledge Chain

```
Problem → Solution → Verification → Skill → Future Reuse
```
