# P3C Batch Intent And Continuity Merge Implementation Plan

Status: `legacy merge writer retired; planning/rejection compatibility remains bounded`

## Ordered Work

1. Freeze P3A/P3B reports and write batch ordering/rejection tests first.
2. Reuse `GameplayCommandEnvelope` only for proposal shaping; the historic
   generic merge is retired because it formerly derived a stream/event from
   free-form payloads and appended under `population.authority`.
3. Extend idempotency, replay and projection tests with deferred receipts and
   scope filtering.
4. Add a focused profile only after concrete owner files and schema migration
   are reviewed.

Stop for a second transaction path, planner persistence, unordered floating
results, a merge that cannot replay from checkpoint plus tail, or any attempt
to restore the retired generic `population.authority` writer. Existing domain
owner fragments are the only production settlement path.
