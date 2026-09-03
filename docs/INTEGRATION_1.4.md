# RouterScan 1.4 integration validation

The 1.4 platform layer is composed through a bounded, offline validation helper.

The integration contract is:

1. A named scan profile supplies limits only; it never grants authorization.
2. A registered worker must advertise the requested capability before a lease is acquired.
3. Evidence records reference finding/signal/probe/detector identities without raw targets or raw signal values.
4. Differential classification operates on opaque fingerprints.
5. Historical analytics consume sanitized observability events and return aggregate buckets only.
6. Plugin contracts are version-checked and remain network-free unless a caller explicitly implements network behavior behind the existing authorization and network policy gates.

The integration test suite is intentionally offline and deterministic. It validates composition and privacy boundaries rather than pretending that a collection of unit tests is a production scan.
