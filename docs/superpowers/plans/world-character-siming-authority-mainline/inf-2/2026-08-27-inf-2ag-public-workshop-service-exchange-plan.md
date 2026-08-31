# INF-2AG Public Workshop Service Exchange Implementation Plan

Status: `implemented and verified narrow vertical; generic service/payment remains blocked`

1. [x] Add the immutable v5 manifest content and adapter-derived declaration/content digest; do not modify v1-v4 packages.
2. [x] Add exact Contract terms, source-bound creation and fulfillment methods and immutable catalog descriptors.
3. [x] Write RED tests for source/policy/party/privacy/revision/idempotency and zero-write boundaries.
4. [x] Add the independent `inf2ag-public-workshop-service-exchange` Harness.
5. [x] Add the exact Economy package-exchange outcome binding and verify fixed 12 `currency:local` debit/credit/settled vector.
6. [x] Verify owner-local append receipts, Contract/Economy full/checkpoint-tail replay and cross-owner non-combination.
7. [x] Synchronize audit, remaining-scope, README, blocker taxonomy, conflict matrix and continuation checkpoint.

Evidence: `24 passed` focused tests, dedicated Harness green, and full
repository pytest `3940 passed`.

No generic service, payment, transfer, market, account, router, registry,
coordinator, settlement authority or second runtime is admitted.
