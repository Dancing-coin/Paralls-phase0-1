# INF-4G Isolated Owner Consequence Projection Plan

Status: `implemented and independently verified 2026-08-14; isolated branch-local projection only`

1. [x] Add RED tests for supply/inspection local consequence projections, rejected
   paths, redaction, replay and production zero writes.
2. [x] Extend only the isolated branch record reducer; derive projection fields from
   the already validated owner fragment without settlement or append.
3. [x] Add dedicated Harness assertions, synchronize all INF-4/August status docs,
   then run focused profiles, diff check and full pytest.

The completion is limited to the isolated projection contract. Production
settlement, a branch receipt/owner, promotion and complete group simulation
remain explicit follow-on blockers.
