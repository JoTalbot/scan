# Definition of done

A pre-observability engineering task is complete only when:

1. The implementation is bounded and fail-closed where authorization matters.
2. Retry/resume behavior is deterministic and idempotent where applicable.
3. Regression tests cover the new behavior and important negative paths.
4. CI verifies the supported runtime floor.
5. Public repository policy does not permit operational secrets into tracked artifacts.
6. Project state and user-facing documentation agree with the implementation.
7. The change is isolated in a reviewable commit/PR before entering `main`.

No telemetry requirement is hidden inside this definition. Observability is the next explicit phase.
