# INF-2AB Tax Payment Owner-Contract Audit Plan

Status: `implemented and independently verified narrow tax-payment vertical; generic Treasury/payment remains blocked`

1. Inspect the existing Economy tax lifecycle, account settlement spine, and
   governed authority catalog. Completed: INF-2Z has source and terminal
   lifecycle evidence, but terminal settlement is account-neutral.
2. Locate the admitted GovernmentTreasuryCollectorAuthority collector identity,
   Economy payer-binding pins, and receipt/replay contract. Completed in the
   exact row-specific admission contract.
3. Write focused RED tests covering success, forged source zero-write,
   account-owner/privacy/revision rejection, idempotency, and full/checkpoint-
   tail replay before implementation. Completed: the focused tax-payment suite
   is green.
4. Implement only the Economy owner fragment and its one existing append
   path; then add a distinct Harness profile/report and synchronize the
   formal/August status. Completed: `infra-economy-government-tax-payment` is
   green.

The generic arbitrary-payment blocker remains separate. This plan records the
completed exact Treasury collector/tax-payment row and does not authorize a
generic Treasury, payment, transfer, settlement, or compensation writer.
