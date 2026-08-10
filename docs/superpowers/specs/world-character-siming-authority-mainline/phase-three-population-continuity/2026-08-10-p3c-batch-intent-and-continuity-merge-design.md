# P3C Batch Intent And Continuity Merge

Status: `design-only; implementation not authorized`

## Purpose And Flow

A bounded planner may propose many actor actions without truth ownership.

```text
profile-scoped inputs -> planner proposals -> GameplayCommandEnvelope
  -> authority validation/SettlementPlan -> append_batch -> receipts
```

Each envelope pins actor/profile and activation refs, policy/package revision,
time window, expected stream revisions, idempotency/correlation keys and claimed
slot/resource references. The planner reads only scope-filtered projections and
receives committed receipts.

## Merge Boundary

Authority orders candidates deterministically, rejects stale or incompatible
claims without partial writes and exposes defer/requeue reasons. Inventory,
facility slot, contract, Survival and organization consequences remain their
owners' adapters. Test shuffled ordering, duplicate batch, stale stream,
exhausted slot, privacy denial and full/checkpoint-tail replay.
