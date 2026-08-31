# INF-2AK Public-Project Budget Close Implementation Plan

Status: `implemented narrow vertical; broader budget lifecycle remains blocked`

1. Register the exact Economy lifecycle descriptor and immutable governed
   catalog row for `public_project_budget_closed@1`.
2. Extend the existing Economy projector with a closure map and strict
   INF-2AI/INF-4AJ provenance validation.
3. Add `close_public_project_budget` through
   `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
4. Keep the row authority-only, single-event, project/facility-bound, terminal
   and account-neutral; derive idempotency and receipt within the existing owner.
5. Verify success, exact/changed duplicate, missing/private/stale/mismatched
   source, forged provenance, receipt, privacy, and full/checkpoint-tail replay.
6. Keep all generic budget lifecycle, release, refund, payment, transfer and
   compensation inputs zero-write.
7. Revalidate closure provenance during projection/replay and fail closed on
   forged or missing source links.

Evidence: `backend/tests/test_inf2ak_public_project_budget_close.py`,
`scripts/verification/verify_inf2ak_public_project_budget_close.py`, and
`.harness/verification/inf2ak-public-project-budget-close-report.json`.
