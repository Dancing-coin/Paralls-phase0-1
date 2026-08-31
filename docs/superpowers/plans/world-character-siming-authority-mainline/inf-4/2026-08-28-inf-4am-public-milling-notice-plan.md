# INF-4AM Public Milling Notice Implementation Plan

Status: `implemented narrow vertical; generic notification and permit semantics remain blocked`

1. [x] Write RED tests for exact INF-4AL activity, provider, facility/project,
   acquisition/jurisdiction, duplicate, privacy and revision pins.
2. [x] Install the immutable Government descriptor/catalog row.
3. [x] Implement the owner-bound verifier and fixed project notice through
   `GameplayCommandEnvelope -> SettlementPlan ->
   GameplayEventStore.append_batch()`.
4. [x] Add Government full/checkpoint-tail notice replay.
5. [x] Add independent Harness and verify receipt, idempotency, privacy,
   zero-write and no permit/social/population/payment expansion.
6. [x] Synchronize governing documents and run focused/full regressions.
7. [x] Revalidate every canonical notice payload during full and checkpoint-
   tail replay; forged immutable partition pins fail closed.

This plan admits one named milling notice only; it is not generic notification,
permit, certificate or project lifecycle authority.
