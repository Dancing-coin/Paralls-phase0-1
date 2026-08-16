# INF-4Z Production Evidence Wage Consumer Implementation Plan

Status: `implemented and verified; one Production-to-Economy consumer only`

1. [x] Add and run focused failing tests for frozen Production worker-scoped
   input, source/privacy/revision pins, and split zero-write, idempotency, and
   replay assertions.
2. [x] Extend only the existing production source-input adapter,
   PopulationPlanner proposal/merge admission, and Economy wage writer. No
   runtime, truth owner, store, scheduler, or generic work mapping is added.
3. [x] Materialize the accepted Economy event through a command envelope and
   SettlementPlan, with actor-only event/outbox visibility and owner receipt.
4. [x] Add standalone Harness evidence, then synchronize INF-4Z, August
   guidance, formal dependency record, and Harness documentation.
5. [x] Rerun predecessor continuation gate, focused tests, profile, registry,
   full pytest (`2698 passed`), and `git diff --check` after synchronization.

Non-goals: wage payment, payroll, non-production evidence, generic work,
compensation, P6 and P7.
