# INF-2F Activation-Released Overheated Expiry Implementation Plan

Status: `implemented and verified 2026-08-14; one exact two-receipt owner row only`

1. [x] Add focused RED tests for the exact released `state:overheated@1`
   pending row: success, exact duplicate, changed duplicate zero-write,
   revision/privacy/unsupported-state/terminal zero-write, scoped projection,
   full/checkpoint-tail replay and separate append receipts.
2. [x] Extend only the existing activation-to-Survival admission fence with the
   exact overheated obligation identity. Preserve `cold` and `dehydrated` as
   separately named rows and reject all other states.
3. [x] Reuse `SurvivalAuthority.build_state_expiry_fragment()` and
   `ObligationSettlementCoordinator`; do not add an activation-owned target
   write, scheduler, store, bus, clock, owner or cross-stream receipt.
4. [x] Add a dedicated Harness profile/report with one explicit assertion per
   capability; rerun predecessor Harness reports and focused replay/privacy
   evidence.
5. [x] Synchronize the INF-2 tree, dependency records, August analysis and
   `docs/harness.md`; run `git diff --check` and the full test suite.
