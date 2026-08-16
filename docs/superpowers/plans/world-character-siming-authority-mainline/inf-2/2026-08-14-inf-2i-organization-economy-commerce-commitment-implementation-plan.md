# INF-2I Organization/Economy Commerce Commitment Plan

Status: `implemented bounded and verified 2026-08-14`

1. [x] Name the fixed Organization, Economy, Inventory and optional Wage owner
   rows, their streams, events, revisions, privacy readers and single append
   receipt boundary in the paired formal design.
2. [x] Add focused RED tests for success, exact duplicate, changed duplicate
   zero-write, stale Organization/Economy revisions, missing/mismatched budget,
   scoped projection/outbox, one append receipt, and full/checkpoint-tail replay.
3. [x] Change only the existing `CommerceAuthority` commitment path as required
   to preserve canonical request idempotency through the existing event store.
4. [x] Add one independent Harness profile/report, with one test selector per
   capability; synchronize the INF-2 tree, root dependency records and August
   analysis without claiming generic settlement.
5. [x] Run focused/dependent suites, the continuation gate, Harness, docs check,
   `git diff --check`, and the full test suite.

Do not create a coordinator writer beyond the existing bounded
`CommerceAuthority`, and do not expand this package to payment or generic
cross-domain policy registration.
