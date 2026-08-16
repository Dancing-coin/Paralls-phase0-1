# P3C Batch Intent And Continuity Merge

Status: `legacy merge writer retired; planning/rejection compatibility remains bounded`

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

Authority orders candidates deterministically and exposes proposal/rejection
reasons. The historic `ContinuityMergeAuthority.merge(PopulationBatchPlan)`
cannot identify a target owner, owner fragment, canonical stream/event family,
scoped projection, revision boundary or owner receipt from a free-form
candidate payload. It is therefore retired as a production writer and returns
`legacy_population_merge_retired` with zero events and zero outbox entries.

Inventory, facility slot, contract, Survival and organization consequences must
use their existing owners' adapters. Formal population writes are limited to
the admitted INF-4Z owner-bound paths, including `merge_world_plan()` and the
separately documented source-specific consumer methods. Test shuffled planning,
legacy zero-write retirement, stale/profile/privacy rejection, and replay of
the remaining owner-authorized paths. No P3C caller may revive a
`population.authority` write path.
