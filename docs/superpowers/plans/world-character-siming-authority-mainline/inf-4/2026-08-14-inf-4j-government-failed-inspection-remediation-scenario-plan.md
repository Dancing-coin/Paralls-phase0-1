# INF-4J Government Failed-Inspection Remediation Scenario Plan

Status: `implemented and verified for one fixed non-production Government remediation row; broader INF-4 remains incomplete`

1. [x] Re-run INF-4I focused/Harness predecessor evidence and record its
   passed-only boundary.
2. [x] Add focused RED tests for one failed inspection scenario record, derived
   remediation identity/action, idempotency, revision/privacy/unknown/passed
   zero writes, outbox, replay, production isolation and promotion rejection.
3. [x] Extend only `GovernmentAuthority` and its existing scenario projection;
   let `BranchPreviewAuthority` submit the already evaluated false candidate.
   Preserve one existing store and the Government envelope/SettlementPlan path.
4. [x] Add a dedicated Harness profile/report with one selector per capability.
   Synchronize the INF-4 trees, root dependency records, August analysis and
   `docs/harness.md`.
5. [x] Run focused tests, INF-4I predecessor profile, full/checkpoint-tail
   replay, `git diff --check`, docs gate and `python -m pytest -q`.

Evidence: [INF-4J Harness report](../../../../../.harness/verification/infra-government-failed-inspection-remediation-scenario-report.json).
