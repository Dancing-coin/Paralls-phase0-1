# INF-1AJ Facility Public-Use Enablement Implementation Plan

Status: `implemented and verified narrow vertical; generic facility availability remains blocked`

1. [x] Write RED tests for the exact operational-verification source, fixed
   oven-only target, payload, duplicate, privacy, revision, and zero-write
   boundaries.
2. [x] Add only the immutable Construction catalog/descriptor row.
3. [x] Implement the owner-bound verifier and one fixed append event through
   `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
4. [x] Extend the existing Construction projector with the exact
   `public_use_status` branch and full/checkpoint-tail replay view.
5. [x] Add an independent Harness and verify receipt, idempotency, privacy,
   revisions, replay, terminal semantics, and no cross-domain effects.
6. [x] Synchronize audit, remaining-scope, README, blocker taxonomy, matrix,
   and continuation checkpoint; run INF-focused and full regression suites.

This plan does not authorize a generic public-use API or any facility-kind
fallback. Only the exact committed `oven` source row is admitted.
