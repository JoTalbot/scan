# Authorization contract

Active scanning and authentication checks are security-sensitive operations. The repository uses an explicit operator-supplied authorization reference as a fail-closed gate.

## Required input

Set:

```text
SCAN_AUTHORIZATION_REF=<ticket-or-assessment-reference>
```

The value identifies the authorization record. It is not a secret and must not contain passwords, API tokens, cookies, or private keys.

## Rules

- Missing or blank authorization reference blocks active operations.
- A discovered target does not create authorization.
- CI and scheduled jobs must receive authorization explicitly from their deployment/operator context.
- Public reports contain a stable target identifier rather than a live target address.
- Credential evidence remains operationally restricted and must not be committed as generated CSV/GZIP artifacts.

The gate is deliberately boring. Security tooling should be boring at the boundary, because improvisation is how incident reports are born.
