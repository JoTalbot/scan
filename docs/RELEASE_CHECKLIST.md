# Release readiness checklist

## Security

- [ ] Active probing has an explicit authorization reference.
- [ ] Target scope is explicit and bounded.
- [ ] Credentials and tokens are supplied outside Git.
- [ ] Public reports are sanitized.
- [ ] CI policy checks are green.

## Distributed execution

- [ ] Every shard has a stable job/shard identity.
- [ ] Failed shards remain resumable.
- [ ] Successful shards are idempotent on retry.
- [ ] The job closes only after all declared shards complete.
- [ ] Concurrency and timeout bounds are enforced.

## Detection

- [ ] Vendor/model detection has regression coverage.
- [ ] Multi-signal evidence is deterministic.
- [ ] Confidence scoring remains bounded.
- [ ] Known false-positive traps are covered.

## CI and documentation

- [ ] Full pytest suite is green on supported Python versions.
- [ ] Security regression suite is green.
- [ ] Source compilation passes.
- [ ] `PROJECT_STATE.json` is valid and current.
- [ ] Architecture and security documentation match the implementation.

## Post-release

- [ ] Observability work is tracked separately from correctness fixes.
- [ ] No production credentials or live findings are copied into public artifacts.
