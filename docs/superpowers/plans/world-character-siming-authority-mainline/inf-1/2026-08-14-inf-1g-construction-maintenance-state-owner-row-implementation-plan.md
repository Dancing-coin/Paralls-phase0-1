# INF-1G Construction Maintenance State Owner Row Implementation Plan

Status: `implemented and verified as one closed Construction owner row; broader August INF-1 closure remains incomplete`

1. [x] Add focused failing tests for the one exact semantic proposal ->
   Construction maintenance-state row, duplicate/revision/privacy/mapping
   rejection, stale closed semantic-vector rejection, project projection, and
   full/checkpoint-tail replay. Every rejection snapshots events, outbox and
   idempotency surfaces before asserting zero write.
2. [x] Extend only existing semantic registry admission, semantic bridge, and
   `ConstructionProductionAuthority` with the fixed owner/stream/event/scope
   contract from the design. Use an owner-built envelope and `SettlementPlan`;
   no generic dispatch or direct store write is permitted.
3. [x] Add a Construction scoped projector event reduction and a dedicated
   Harness profile with separate assertion execution per capability.
4. [x] Synchronize INF-1/root/August/Harness records and run focused tests,
   the profile, full pytest, continuation gate, and `git diff --check`.
   The final owner-boundary review required and then approved direct-owner
   stale-vector and unacquired-facility zero-write regressions; an acquired
   facility without a started run remains a valid settlement case.
