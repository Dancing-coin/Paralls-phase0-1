# INF-4U Municipal Drought Assessment Certificate Plan

Status: `implemented and verified narrow vertical`

1. Re-read the exact completed INF-3S municipal assessment contract, its fixed
   terms/evidence, advisory-derived identity and contract revision.
2. Derive one deterministic asset/right and grant it only to the fixed district
   organization through the existing Ownership owner.
3. Append only one authority-only `right_granted` event through
   `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
4. Verify catalog admission, source/revision/idempotency zero-write,
   append receipt, Ownership full/checkpoint-tail replay and independent Harness.

No title transfer, payment, inspection decision, social/population fact,
compensation, fanout or generic certificate authority is in scope.
