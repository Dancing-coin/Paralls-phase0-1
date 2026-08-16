# INF-2R Payroll Owner-Contract Catalog Plan

Status: `implemented and independently verified; broader INF-2 remains incomplete`

1. [x] Re-run the predecessor payroll/window focused test, its independent
   Harness profile, and the owner-only obligation focused suite.
2. [x] Add RED tests for the two catalog rows and for Organization pre-append
   contract rejection with zero writes.
3. [x] Add the two immutable catalog rows, including mixed fixed outbox
   metadata for Economy wage payment.
4. [x] Require the Organization row before each window append and require the
   Economy row before its existing payment batch. Do not add a coordinator.
5. [x] Add independent catalog-consumption Harness selectors, rerun focused,
   predecessor, full/checkpoint-tail replay, `git diff --check`, and root
   `python -m pytest -q`.
6. [x] Synchronize INF-2 README, the August timing guidance, mainline audit,
   Harness documentation, and evidence report with bounded status.

## Stop Condition

If either contract cannot name the existing owner, event family, stream,
privacy, revision/idempotency handling, append-derived receipt, and replay
reader, remove it from this plan and retain unsupported-input zero-write.
