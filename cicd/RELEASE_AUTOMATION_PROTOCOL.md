# Release Automation Protocol

## Lifecycle

```
Build
  ↓
Test
  ↓
Security Validation
  ↓
Create Release
  ↓
Deploy
  ↓
Health Check
  ↓
Promote or Rollback
```

## Goals

- repeatable production releases
- rollback capability
- deployment verification
- integration with observability and governance

## Release States

```
pending → testing → production → rollback
```
