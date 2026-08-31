# INF-2AF Public-Project Budget Commitment Implementation Plan

Status: `implemented and verified narrow vertical; generic payment/transfer remains blocked`

1. [x] Write RED tests for the exact INF-1AK source and fixed 12-unit
   authority-only budget commitment.
2. [x] Add only the immutable Economy catalog/descriptor row.
3. [x] Implement source/head/revision verifier and one fixed Economy append
   event through `GameplayCommandEnvelope -> SettlementPlan -> append_batch()`.
4. [x] Extend the Economy projector with the commitment projection and
   full/checkpoint-tail replay.
5. [x] Add an independent Harness and verify zero-write, privacy,
   idempotency, receipt, source pins, and no account mutation.
6. [x] Synchronize audit, remaining-scope, README, taxonomy, matrix,
   checkpoint, and run INF/full regression suites.

This is a non-payment planning fact. It must not be generalized into account
reservation, transfer, reimbursement, material purchase, or a budget registry.
