# INF-4AL Public Milling Activity Implementation Plan

Status: `implemented narrow vertical; generic activity, attendance and social truth remain blocked`

1. [x] Write RED tests for exact fulfilled INF-2AL source, fixed provider,
   mill-reinforced facility/project binding, duplicate, privacy and revision.
2. [x] Install the immutable Organization descriptor/catalog row.
3. [x] Implement the owner-bound verifier and one fixed project activity event
   through `GameplayCommandEnvelope -> SettlementPlan ->
   GameplayEventStore.append_batch()`.
4. [x] Add the Organization full/checkpoint-tail replay reader.
5. [x] Add independent Harness and verify receipt, idempotency, privacy,
   zero-write and no social/population/payment expansion.
6. [x] Synchronize governing documents and run focused/full regressions.
7. [x] Revalidate every canonical activity payload during full and checkpoint-
   tail replay; forged immutable partition pins fail closed.

This plan admits one named public-milling activity only; it is not a generic
activity, attendance, social, population or settlement capability.
