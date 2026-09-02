# Resumable step runner

`resumable_runner.py` is the narrow adapter between an existing authorized
execution path and `job_state.py`.

## Contract

A caller must provide all three environment values:

- `SCAN_AUTHORIZATION_REF`: explicit authorization reference.
- `SCAN_SCOPE_REF`: explicit scope reference.
- `SCAN_JOB_ID`: stable operational job identifier.

The runner refuses to execute without them. Authorization is never inferred
from targets, scan results, or discovered router data.

Before execution it checks durable step state. A completed step is skipped.
After execution it records completion only when the subprocess exits with code
`0`. Failed or interrupted steps remain resumable.

Only operational references and completion metadata are persisted by the job
state layer. Targets, credentials, passwords, usernames, tokens, and other
secret material do not belong in this state.

The next integration stage is to replace direct worker/orchestrator subprocess
launches with this adapter while preserving their existing authorization gates
and bounded execution settings.
