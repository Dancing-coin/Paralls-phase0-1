# INF-4W Production Work-Order Fulfillment Implementation Plan

Status: `implemented and verified narrow vertical; generic work-order lifecycle remains blocked`

1. [x] Write RED tests for exact INF-4V source, fixed fulfillment payload,
   duplicate/revision/privacy zero-write, receipt, and full/tail replay.
2. [x] Add the immutable Organization catalog/descriptor row only.
3. [x] Implement the strict Organization verifier and one fixed append event
   through `GameplayCommandEnvelope -> SettlementPlan -> append_batch()`.
4. [x] Add the owner-local fulfillment projection/replay view and independent
   Harness.
5. [x] Run focused INF tests, full pytest, docs/ruff/compileall/diff checks and
   update audit, remaining-scope, README, taxonomy, matrix, and checkpoint.

The row remains isolated from INF-4V acceptance, Economy wage/payment,
production output, branch promotion, and generic task APIs.

Evidence: the independent INF-4W Harness runs the exact INF-4W test subset;
the INF-4V Harness runs only its own acceptance subset.
