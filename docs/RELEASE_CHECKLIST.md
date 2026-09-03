# Release readiness checklist

## Security

- [x] Active probing has an explicit authorization reference.
- [x] Target scope is explicit and bounded.
- [x] Credentials and tokens are supplied outside Git.
- [x] Current public reports/history-facing artifacts are sanitized; live targets and credential evidence are excluded from the current tree.
- [x] CI policy checks are green on the remediation branch.
- [ ] Historical Git objects containing superseded public findings are rewritten/removed and independently revalidated.
- [ ] No open P0 security blockers remain after historical remediation.

## Distributed execution

- [x] Every shard has a stable job/shard identity.
- [x] Failed shards remain resumable.
- [x] Successful shards are idempotent on retry.
- [x] The job closes only after all declared shards complete.
- [x] Concurrency and timeout bounds are enforced.

## Detection

- [x] Vendor/model detection has regression coverage.
- [x] Multi-signal evidence is deterministic.
- [x] Confidence scoring remains bounded.
- [x] Known false-positive traps are covered.

## CI and documentation

- [x] Full pytest suite is green on supported Python versions on the remediation branch.
- [x] Security regression suite is green on the remediation branch.
- [x] Source compilation passes on the remediation branch.
- [x] `PROJECT_STATE.json` is valid and current.
- [x] Architecture, observability, security, and release documentation match the implementation.
- [x] Public artifact regression tests cover credentials and target addresses.

## Post-release

- [x] Observability work is tracked separately from correctness fixes.
- [x] No production credentials or live findings are copied into current public release artifacts.

## Release decision

**Production release is blocked until historical Git remediation is completed and the complete release gate is revalidated.**

Current baseline: `main` after public-artifact remediation.
Historical remediation tracker: Issue #7.
