# RouterScan pre-observability architecture contract

## Scope

This document defines the production boundary before the observability phase. It covers authorization, resumable distributed execution, deterministic detection, CI gates, and release hygiene.

## Execution contract

1. Every active scan starts with an explicit `SCAN_AUTHORIZATION_REF` and `SCAN_SCOPE_REF`.
2. Missing authorization fails closed.
3. Scan arguments are passed as argv values, not shell-interpolated target commands.
4. A shard becomes complete only after its child process exits successfully.
5. Re-running a completed shard is idempotent and must not launch it again.
6. A job becomes `completed` only after all declared shards are complete.
7. Job state contains operational references and status only. Targets, passwords, tokens, headers, and private keys are never persisted.

## Detection contract

Detection is passive with respect to network activity. It consumes already collected HTTP artifacts and returns a deterministic result containing:

- vendor and device type;
- optional model;
- primary matched source;
- supporting matched sources;
- evidence signals;
- bounded score and score confidence.

False-positive traps reduce confidence instead of producing an authorization bypass or active follow-up request.

## CI contract

Every change must pass:

- the complete pytest suite;
- Python compilation checks;
- the security regression suite;
- repository policy checks for obvious credential material;
- project-state JSON validation.

The supported CI Python floor is 3.10; the matrix currently exercises 3.10, 3.11 and 3.12.

## Release boundary

The project is not considered release-ready merely because tests pass. A release requires:

- explicit authorization controls documented and enforced;
- public artifacts sanitized;
- resumable shard semantics tested;
- detection regressions covered;
- CI gates green;
- no operational secrets in Git;
- user-facing documentation updated.

Observability is intentionally a separate phase. Metrics, tracing and centralized event sinks must build on these stable contracts rather than compensate for missing correctness guarantees.
