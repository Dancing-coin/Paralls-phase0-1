# INF-3M Implementation Plan

Status: `completed and verified`

1. [x] Add RED tests for event-derived deterministic planning, source/privacy and
   no-target rejection, owner-only append, idempotency/revision, outbox scope,
   and replay equivalence.
2. [x] Add the closed planner policy and immutable plan model to
   `EcologyHazardAuthority`'s existing ecology runtime.
3. [x] Implement source-event revalidation and deterministic canonical-neighbor
   derivation; delegate commit to the existing wave owner fragment/batch path.
4. [x] Add an independent Harness profile and verification script with one pytest
   selector per capability.
5. [x] Update INF-3 README, August guidance, main audit/spec status, then run focused
   tests, Harness, replay checks, `git diff --check`, and the full pytest suite.

Constraints: no new runtime, store, bus, clock, scheduler, registry, consumer
owner, or direct projection writer. All formal writes remain
`EcologyHazardAuthority -> OwnerAuthorizedFragment -> append_batch -> outbox/replay`.
