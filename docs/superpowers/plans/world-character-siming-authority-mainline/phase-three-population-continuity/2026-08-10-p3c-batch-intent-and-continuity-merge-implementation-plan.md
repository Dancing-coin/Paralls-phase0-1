# P3C Batch Intent And Continuity Merge Implementation Plan

Status: `design-only; implementation not authorized`

## Ordered Work

1. Freeze P3A/P3B reports and write batch ordering/rejection tests first.
2. Reuse `GameplayCommandEnvelope` and the current pure `SettlementPlan`
   adapter; no planner API appends events.
3. Extend idempotency, replay and projection tests with deferred receipts and
   scope filtering.
4. Add a focused profile only after concrete owner files and schema migration
   are reviewed.

Stop for a second transaction path, planner persistence, unordered floating
results or a merge that cannot replay from checkpoint plus tail.
