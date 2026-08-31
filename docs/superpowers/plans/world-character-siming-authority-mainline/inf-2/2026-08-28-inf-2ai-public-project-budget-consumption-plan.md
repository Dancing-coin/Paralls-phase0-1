# INF-2AI Public-Project Budget Consumption Implementation Plan

Status: `implemented and verified narrow vertical; generic budget/payment remains blocked`

1. Register the exact Economy descriptor and governed catalog row for
   `public_project_budget_consumed@1`; keep the catalog immutable/read-only.
2. Extend the existing Economy projection with a consumed-reservation map and
   provenance validation for the fixed INF-2AF/INF-2AH/INF-4AG source vector.
3. Add the owner-bound `consume_public_project_budget` method through
   `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
4. Keep amount, currency, reservation, project/facility binding, privacy,
   event, receipt, replay and idempotency owner-derived and fixed.
5. Verify success, missing/private/stale/mismatched source, exact/changed
   duplicate, authority privacy, append receipt, and full/checkpoint-tail replay
   with focused tests and an independent Harness.
6. Synchronize audit, remaining-scope, README, blocker taxonomy and checkpoint.

The row is intentionally a consumed marker, not account mutation or a generic
reserve/release/payment API. Existing frozen packages and all other INF rows
remain unchanged.

Evidence: `backend/tests/test_inf2ai_public_project_budget_consumption.py`,
`scripts/verification/verify_inf2ai_public_project_budget_consumption.py`, and
`.harness/verification/inf2ai-public-project-budget-consumption-report.json`.
