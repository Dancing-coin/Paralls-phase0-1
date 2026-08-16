# INF-4AA P3D Schedule-Gated Supply Reclosure Design

Status: `implemented and independently verified; one existing Organization supply row only`

## Scope

This package corrects the stale P3D bakery-district vertical.  It replaces the
retired generic `ContinuityMergeAuthority.merge()` call with the already
admitted event-derived path for one released `schedule_gated_supply` row.

The identity source remains the existing `CharacterProfile` registry.  The
activation authority owns only activation facts on `population:{world_ref}`;
the existing `OrganizationAuthority` remains the sole owner of the resulting
commerce commitment truth on its existing organization stream.

## Write contract

The vertical first records and releases the exact activation pending row.  The
event-derived release is then admitted by
`ContinuityMergeAuthority.merge_released_schedule_gated_supply()`, which
revalidates profile, lock, plan digest, source vectors, privacy, and target
revision before delegating to the existing Organization fragment builder.

```text
ProfileActivationAuthority -> population activation events -> append/outbox/replay
released pending projection -> OrganizationAuthority fragment
-> GameplayEventStore.append_batch() -> Organization outbox/replay/scoped projection
```

There is no population truth writer, generic batch merge, second runtime,
clock, scheduler, event store, or branch writeback.

## Evidence and limits

`phase3d-bakery-district-population` independently asserts successful owner
settlement, duplicate idempotency, revision conflict, privacy denial,
zero-write rejection, and full/checkpoint-tail replay equivalence.  Its report
is [P3D reclosure evidence](../../../../../.harness/verification/phase3d-bakery-district-population-report.json).

This reclosure supersedes only P3D's obsolete committed generic-batch claim.
Generic `work`, arbitrary population intents, a population/NPC/social truth
owner, production-equivalent branch evolution, and complete group simulation
remain unimplemented and blocked by their separate owner contracts.
