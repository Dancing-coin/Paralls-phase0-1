# INF-2AB Tax Payment Owner-Contract Audit Plan

Status: `blocked after read-only contract audit`

1. Inspect the existing Economy tax lifecycle, account settlement spine, and
   governed authority catalog. Completed: INF-2Z has source and terminal
   lifecycle evidence, but terminal settlement is account-neutral.
2. Locate a canonical collector account, its existing account-holder owner,
   and a receipt/replay contract. Blocked: none exists in the current
   authority catalog or formal INF-2 contract tree.
3. Once that contract exists, write focused RED tests covering success,
   forged source zero-write, account-owner/privacy/revision rejection,
   idempotency, and full/checkpoint-tail replay before implementation.
4. Implement only the Economy owner fragment and its one existing append
   path; then add a distinct Harness profile/report and synchronize the
   formal/August status.

No code, test, Harness profile, or capability completion is produced by this
audit. It is an owner-contract blocker record, not an implementation package.
