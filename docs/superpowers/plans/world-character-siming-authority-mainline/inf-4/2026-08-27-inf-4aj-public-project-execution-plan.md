# INF-4AJ Public Project Execution Implementation Plan

Status: `implemented and verified narrow vertical; generic project execution remains blocked`

1. [x] Add the immutable Organization descriptor and governed contract row.
2. [x] Write RED tests for the exact INF-4AG + INF-2AI source vector,
   project privacy, revisions, idempotency, duplicate, receipt and replay.
3. [x] Implement one owner-bound Organization append through the existing
   command-envelope, settlement-plan and event-store spine.
4. [x] Keep the target semantic fixed at `funded_and_executed` and exclude
   payment/debit/release/refund/material/inventory/output/attendance/social/
   population semantics.
5. [x] Add an independent Harness profile and verification script.
6. [x] Synchronize row README, mainline README, audit, remaining-scope,
   blocker taxonomy and continuation checkpoint.

Evidence: `backend/tests/test_inf4aj_public_project_execution.py`,
`scripts/verification/verify_inf4aj_public_project_execution.py`, and
`.harness/verification/inf4aj-public-project-execution-report.json`.
