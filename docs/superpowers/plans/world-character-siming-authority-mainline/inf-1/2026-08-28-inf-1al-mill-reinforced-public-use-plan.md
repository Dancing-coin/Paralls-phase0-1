# INF-1AL Mill-Reinforced Public-Use Implementation Plan

Status: `implemented narrow vertical; generic facility availability remains blocked`

1. [x] Write RED tests for the exact completed-run verification source,
   frozen v2 reinforcement provenance, mill-reinforced kind, duplicate,
   privacy, revision and zero-write boundaries.
2. [x] Add the immutable Construction catalog and owner-operation descriptor
   for this existing-row extension.
3. [x] Implement the row-specific owner verifier and one fixed append event
   through `GameplayCommandEnvelope -> SettlementPlan ->
   GameplayEventStore.append_batch()`.
4. [x] Extend the existing Construction projector with the exact row-ref and
   reinforcement-provenance branch; preserve full/checkpoint-tail equivalence.
5. [x] Add the independent Harness and verify receipt, idempotency, privacy,
   revisions, replay, terminal semantics and no cross-domain effects.
6. [x] Synchronize the governing audit, remaining-scope, README, taxonomy,
   matrix and continuation checkpoint; run focused and full regressions.

This plan is an existing-row extension for `mill_reinforced` only. It does
not authorize a generic facility-kind public-use operation.
