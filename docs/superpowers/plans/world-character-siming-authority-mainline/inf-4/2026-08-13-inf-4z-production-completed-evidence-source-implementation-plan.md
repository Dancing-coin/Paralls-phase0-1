# INF-4Z Production Completed-Evidence Source Implementation Plan

Status: `implemented and verified; source prerequisite only`

1. [x] Add and run focused failing tests for immutable worker-contribution
   linkage, canonical Production evidence append, actor scope/redaction,
   empty/untrusted/mismatched/stale zero-write, idempotency and replay.
2. [x] Extend only `ConstructionProductionAuthority`, its projector and
   existing production stream/outbox. The formal write path is
   `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
   Economy and PopulationPlanner remain unchanged.
3. [x] Add an immutable scoped evidence view and verify its production stream
   revision/vector and projection hash across full/checkpoint-tail replay.
4. [x] Add the standalone Harness profile/report with one focused pytest
   invocation per capability, then synchronize INF-4Z and August analysis.
5. [x] Re-run predecessor continuation gate, focused tests, Harness, registry,
   full pytest (`2688 passed`) and `git diff --check` after document
   synchronization.

Non-goals: wage accrual, payroll, direct actor completion, generic work mapping,
non-production evidence kinds, compensation, P6 and P7.
