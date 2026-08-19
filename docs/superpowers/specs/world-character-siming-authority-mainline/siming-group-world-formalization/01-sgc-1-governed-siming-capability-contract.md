# SGC-1 Governed Siming Capability Contract

Status: `proposed; owner row selection and contract approval required`

## Scope

This package governs how Siming turns a scoped observation into a typed intent
for one already admitted owner operation. It does not create a Siming owner,
router, registry or settlement authority.

## Contract

`GovernedAuthorityContractCatalog` is the only catalog. One immutable entry
must bind: `capability_ref/version`, caller eligibility, input schema, reader
scope, source event/vector, policy revision, fixed owner/fragment, fixed
stream/event family, expected revision rule, privacy projection, idempotency
key, receipt reader, terminal/retry behavior and compensation disposition.

The operation is:

`scoped read-set -> candidate -> catalog admission -> owner validation ->
SettlementPlan -> append_batch -> receipt/outbox/replay`.

Unknown ref, version mismatch, schema mismatch, caller-selected owner/stream,
scope widening, stale source, stale target or changed duplicate must reject
before `SettlementPlan` construction and perform zero production writes.

## Evidence contract

Focused tests must cover accepted success, all rejection reasons, exact and
changed duplicate behavior, privacy-safe receipt, full replay and
checkpoint-tail replay. The independent Harness selector must prove the same
cases without monkeypatching a second writer.

## Dependencies and non-goals

Depends on an existing owner row with a complete contract. If discovery does
not find one, the package records `owner-contract blocked` and stops. It does
not approve a new owner merely because the Siming flow is well specified.
