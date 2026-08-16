# INF-C4 Ecology Consumer Admission Contract

Status: `implemented and independently verified as a finite read-only substrate; broader INF-3 remains incomplete`

## Scope

`EcologyConsumerAdmissionCheck` centralizes the common pre-fragment checks for
already-registered weather-front consumer rows.  It reads the existing
`GameplayEventStore` and `GovernedAuthorityContractCatalog`, then returns an
immutable check result.  It cannot issue opaque admissions, register a row,
select a target owner, construct a fragment, append an event, or store a
receipt.

The first two reusers are the existing Construction maintenance and
Organization supply owners.  Each preserves its opaque admission check and
domain payload validation; each still constructs its own fragment and submits
only through its existing `GameplayEventStore.append_batch()` path.

## Closed contract

The check admits only a pre-existing `ecology_consumer` catalog row and
validates source event identity/type/stream/revision/project visibility,
target owner/stream/event/scope, current target revisions, a non-empty
idempotency key, receipt reader, and replay reader.  Unknown contracts,
forged owner/stream/scope, private or stale sources, and stale target revisions
return rejection before target fragment construction and therefore before any
target write.

```text
Ecology source evidence + opaque admission
-> EcologyConsumerAdmissionCheck (read-only)
-> existing target owner fragment
-> GameplayCommandEnvelope / SettlementPlan
-> GameplayEventStore.append_batch() -> outbox/replay/scoped projection
```

## Evidence and non-goals

`infra-ecology-consumer-admission-contract` independently proves two-owner
reuse, forged owner/stream/scope/source zero-write, target revision zero-write,
target-owner duplicate idempotency, privacy denial, and full/checkpoint-tail
replay.  Evidence is
`.harness/verification/infra-ecology-consumer-admission-contract-report.json`.

This package does not create a generic consumer registry, generic fanout,
pricing/payment logic, retry/compensation authority, scheduler, second store,
or Ecology write capability over Construction, Organization, Economy, body,
social, or population truth.
