# INF-4AG Public Workshop Activity Implementation Plan

Status: `implemented and verified; Goal active; August INF A-D not complete`

1. [x] Add the fixed Organization activity descriptor/catalog row.
2. [x] Write RED tests for exact Contract source, provider/facility/project binding, privacy, revision, idempotency, duplicate, and zero-write boundaries.
3. [x] Implement the owner-bound Organization append branch and replay reader.
4. [x] Add the independent `inf4ag-public-workshop-activity` Harness.
5. [x] Verify append-derived receipt, full/checkpoint-tail replay, and isolation from payment/social/population semantics.
6. [x] Synchronize audit, remaining-scope, README, blocker taxonomy, conflict matrix and checkpoint.

Evidence: `19 passed` focused/catalog tests and green independent Harness.

The branch is exact-row only; no generic activity, attendance, social fact,
population writer, router, registry, coordinator or cross-owner receipt is
allowed.
