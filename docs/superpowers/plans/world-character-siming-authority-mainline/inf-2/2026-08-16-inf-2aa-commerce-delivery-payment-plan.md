# INF-2AA Commerce Delivery Payment Plan

Status: `implemented and independently verified`

1. [x] Add focused RED tests for payment and compensation using only committed
   existing Inventory delivery and Economy obligation/reservation evidence.
2. [x] Add a closed Economy payment intent and authority-only replay projection;
   neither can append directly.
3. [x] Let `EconomyAuthorityService` revalidate the complete source and target
   vector, build its own Economy fragment, then append exactly once through the
   existing envelope/SettlementPlan spine.
4. [x] Add an immutable governed contract row and pre-append owner gate for the
   two payment terminal families.
5. [x] Prove success, zero-write rejection, duplicate/idempotency, revision,
   privacy, receipt, full replay, checkpoint-tail replay, and compensation with
   an independent Harness profile.
6. [x] Synchronize the INF-2 index, formal mainline audit, August analysis, and
   package evidence after verification.

Non-goals: policy registration, arbitrary payment amount or account routing,
reservation release, generic compensation/retry, a Commerce truth store, a
second runtime/store/bus/clock/scheduler, and branch/population work.
