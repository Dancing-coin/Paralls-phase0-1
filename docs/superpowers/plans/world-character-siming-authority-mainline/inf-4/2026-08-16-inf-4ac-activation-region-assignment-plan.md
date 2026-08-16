# INF-4AC Activation-Owned Profile Region Assignment Plan

Status: `implemented and independently verified`

1. [x] Add focused RED tests for one active profile assignment, exact duplicate
   replay, stale activation revision, forged/private Ecology evidence, inactive
   profile, scoped read privacy, and full/checkpoint-tail replay.
2. [x] Extend only `ProfileActivationAuthority` with an owner-built
   `population.activation.region_assigned` fragment using the existing command,
   settlement-plan and event-store spine.
3. [x] Add an independent Harness profile/report with one explicit assertion
   for every accepted and zero-write boundary.
4. [x] Sync INF-4/INF-1 indexes, August analysis, completion audit and the
   dependency matrix without claiming a Survival consumer is complete.
5. [x] Run focused tests, the independent Harness, `git diff --check`, and the
   full pytest suite.

Verification completed on 2026-08-16: focused tests, independent Harness,
`git diff --check`, and `python -m pytest -q` (`3439 passed in 70.92s`).
