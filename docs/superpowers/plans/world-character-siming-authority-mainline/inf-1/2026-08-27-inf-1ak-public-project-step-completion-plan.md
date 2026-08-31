# INF-1AK Public-Project Step Completion Implementation Plan

Status: `implemented and verified narrow vertical; generic project/task lifecycle remains blocked`

1. [x] Write RED tests for the exact Organization fulfilled source and fixed
   public-project work-order literal.
2. [x] Add only the immutable Construction catalog/descriptor row.
3. [x] Implement the source-bound verifier and one Construction append event
   through `GameplayCommandEnvelope -> SettlementPlan -> append_batch()`.
4. [x] Extend the existing Construction projector with completed project-step
   refs and full/checkpoint-tail replay.
5. [x] Add an independent Harness and verify privacy, source/target revisions,
   idempotency, receipt, duplicate and terminal zero-write behavior.
6. [x] Synchronize mainline audit, remaining-scope, README, taxonomy, matrix,
   and checkpoint; run INF-focused and full regression suites.

The row is fixed to `project-step:public-project:workshop-bench@1`; it is not a
generic work-order or project-progress API.
