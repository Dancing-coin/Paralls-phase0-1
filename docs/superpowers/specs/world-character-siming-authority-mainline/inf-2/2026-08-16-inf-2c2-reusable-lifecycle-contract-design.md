# INF-2C2 Reusable Lifecycle Contract

Status: `implemented and focused-verified; reusable substrate only`

## Decision

`ObligationLifecycleRegistration` is the sole closed contract for lifecycle
operation admission. The contract exposes a bounded `event_type_for()` lookup
for settle, cancel, expire, retry and compensate. It does not create events,
select an owner, or append a batch.

`ObligationSettlementCoordinator.from_closed_registry()` is the explicit
reusable entry point for the canonical existing-owner catalog. The legacy
constructor remains empty by default so callers that do not name an owner
contract continue to receive zero-write rejection.

The `ObligationLifecycleProjection` remains event-derived and read-only. It
reconstructs open and terminal lifecycle state from committed owner events and
supports bounded due views and checkpoint-tail replay without a lifecycle
store, scheduler or second clock.

## Existing consumers

- Survival state expiry uses the same registration shape for open, settle,
  retry and compensate.
- Economy wage and scheduled-transfer obligations use the same shape for
  settle, expire, retry and compensate where the owner contract admits them.
- Construction and ecology remain separately registered rows; this package
  does not widen their terminal capabilities.

## Boundaries

- Unknown policy, forged registration, widened event family, owner, stream,
  revision or privacy mismatch remains zero-write.
- Owner authorities still build fragments and call their own
  `commit_obligation_batch()`.
- The coordinator remains planner-only; it never calls
  `GameplayEventStore.append_batch()`.

## Evidence

Focused evidence is recorded by
`scripts/verification/verify_infra_reusable_lifecycle_contract.py` and the
independent profile
`.harness/profiles/infra-reusable-lifecycle-contract.json`.
