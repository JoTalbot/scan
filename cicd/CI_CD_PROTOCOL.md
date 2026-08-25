# CI/CD Protocol

Pipeline lifecycle:

```
Commit
 ↓
Build
 ↓
Tests
 ↓
Security Checks
 ↓
Artifact
 ↓
Release Gate
 ↓
Deploy
```

Goals:
- repeatable releases;
- automated validation;
- production safety gates.
