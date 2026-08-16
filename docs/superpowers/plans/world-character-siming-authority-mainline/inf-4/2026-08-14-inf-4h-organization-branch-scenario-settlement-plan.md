# INF-4H Organization Branch Scenario Settlement Plan

Status: `implemented and verified 2026-08-14; one Organization-owned supply scenario row only`

1. [x] Add focused failing tests for the one accepted `supply` branch proposal:
   Organization-owned scenario append, duplicate idempotency, stale revision,
   privacy/wrong-input zero write, scenario checkpoint-tail replay, production
   replay isolation and unsupported promotion.
2. [x] Add only an Organization-owned scenario proposal/settlement method on
   `gameplay:organization_branch:{branch_ref}:{organization_ref}`. It must use
   a `GameplayCommandEnvelope` and existing `SettlementPlan`/event store path.
3. [x] Let `BranchPreviewAuthority` propose/read this row without gaining an
   append API. Keep all other candidate kinds zero-write rejected.
4. [x] Add one independent Harness assertion per capability and preserve a
   report. Synchronize INF-4 README, root design/plan, August analysis and
   `docs/harness.md` only after all evidence is green.
5. [x] Run predecessor profiles, focused tests, docs Harness, `git diff --check`
   and `python -m pytest -q`.

Evidence: `.harness/verification/infra-organization-branch-scenario-settlement-report.json`.
