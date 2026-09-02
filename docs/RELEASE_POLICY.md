# RouterScan Release Policy

## Versioning

RouterScan uses semantic versioning for public releases: `MAJOR.MINOR.PATCH`.

- **MAJOR**: incompatible CLI, API, state-schema, or operational-contract changes.
- **MINOR**: backward-compatible capabilities or completed roadmap phases.
- **PATCH**: backward-compatible fixes, documentation corrections, and security hardening that do not change the public contract.

Development snapshots may use descriptive suffixes such as `-observability`, but a release version must be a stable `MAJOR.MINOR.PATCH` value.

## Release gates

A production release must satisfy all of the following:

1. `PROJECT_STATE.json` is valid and reflects the actual implementation.
2. Supported Python versions pass the complete test suite.
3. Security regression checks pass.
4. Source compilation passes.
5. Active probing remains fail-closed and requires explicit authorization and bounded scope.
6. Public reports and synchronized artifacts contain no credentials or raw sensitive evidence.
7. Resumable jobs remain shard-idempotent and only complete after all declared shards finish.
8. Observability remains opt-in and privacy-safe.
9. Documentation describes the shipped behavior and known limitations.
10. No open P0 security finding remains.

## Release process

1. Complete the implementation batch on a dedicated branch.
2. Update `PROJECT_STATE.json`, backlog, changelog, and release notes.
3. Run the full CI/security gates on the release candidate.
4. Review the release checklist and confirm no unresolved blockers remain.
5. Merge only when required gates are green and no P0 blocker remains.
6. Create a Git tag matching the stable version, for example `v1.3.0`.
7. Publish release notes without live targets, credentials, raw HTTP artifacts, or private telemetry.

## Current status

`1.3.0` is prepared for production release. `SCAN-SEC-004` has been resolved by sanitizing public report/status artifacts and adding regression coverage against credential evidence and target addresses.
