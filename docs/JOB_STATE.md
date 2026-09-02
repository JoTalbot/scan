# Resumable Job State

`job_state.py` is the shared state primitive for long-running scan jobs.

## Contract

- Every active job has a stable `job_id`.
- Active work requires both an explicit `authorization_ref` and a `scope_ref`.
- Completed steps are recorded once, so retrying a worker does not duplicate them.
- A completed job remains completed when the same job is resumed.
- Writes use a temporary file plus `os.replace()` to avoid partially written JSON.
- State stores operational references only. Target addresses, credentials, tokens, and secrets are forbidden.

This is deliberately small. It provides a common persistence contract without coupling the scanner to a specific database or queue.
