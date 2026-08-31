# INF-4AH Public Workshop Notice Implementation Plan

Status: `implemented and verified; Goal active; August INF A-D not complete`

1. [x] Add the exact Government notice contract and immutable catalog descriptor.
2. [x] Write RED tests for activity provenance, facility/project/jurisdiction binding, privacy, revision, idempotency, duplicate and zero-write behavior.
3. [x] Implement the Government notice append branch and replay reader.
4. [x] Add the independent `inf4ah-public-workshop-notice` Harness.
5. [x] Verify append-derived receipt, full/checkpoint-tail replay and payload redaction.
6. [x] Synchronize audit, remaining-scope, README, blocker taxonomy, conflict matrix and checkpoint.

Evidence: `19 passed` focused tests and green independent Harness.

The row is exact and terminal. No generic notice, router, registry,
coordinator, social/population writer or combined receipt is admitted.
