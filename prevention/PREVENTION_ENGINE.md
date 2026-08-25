# Prevention Engine

Purpose: convert repeated repair patterns into automatic scan rules.

Flow:

```
Repair History
    ↓
Pattern Detection
    ↓
Rule Generation
    ↓
Future Scan Prevention
```

Lifecycle:

```
Detect → Repair → Verify → Learn → Prevent → Scan
```

Rules:
- repeated issues become preventive checks;
- generated rules are stored as reusable knowledge;
- future scans validate prevention rules.
