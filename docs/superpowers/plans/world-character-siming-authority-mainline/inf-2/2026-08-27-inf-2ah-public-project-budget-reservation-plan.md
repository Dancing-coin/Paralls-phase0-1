# INF-2AH Public-Project Budget Reservation Implementation Plan

Status: `implemented and verified narrow vertical; generic budget/payment remains blocked`

1. [x] Write RED tests for one unique owner-derived `currency:local` account,
   missing/multiple account, insufficient funds, duplicate, changed duplicate,
   privacy, source binding and revision zero-write cases.
2. [x] Add only the immutable Economy descriptor/catalog row for INF-2AH.
3. [x] Implement the owner-bound verifier: consume only the exact INF-2AF
   commitment, reread committed acquisition, derive the unique owner account,
   and reject all caller-selected coordinates before append.
4. [x] Append exactly one `budget_reserved@1` event through
   `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`;
   pin Economy and Construction facility streams in the same read set.
5. [x] Add the authority-only reservation projection with full/checkpoint-tail
   replay and append-derived receipt; projector revalidates pinned commitment
   and acquisition provenance before rebuilding the row.
6. [x] Add the independent Harness and verify source, account, privacy,
   revision, idempotency, receipt, zero-write and replay evidence.
7. [x] Synchronize audit, remaining-scope, README, blocker taxonomy, matrix and
   checkpoint. Preserve generic budget/payment/transfer as blocked.

This plan does not authorize generic budget reservation, account selection,
payment, transfer, release, reimbursement, or settlement behavior.
