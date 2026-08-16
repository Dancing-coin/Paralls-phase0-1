# INF-1A Survival State Obligation Lifecycle Implementation Plan

Status: `implemented and verified 2026-08-13; one Survival-owned row only`

1. [x] Add focused failing tests for a Survival-owned scheduled state: apply,
   stack policies, obligation opening, due expiry, dispel/transform cancellation,
   idempotency, revision/privacy rejection and replay.
2. [x] Extend only `SurvivalAuthority`, its event-derived projector and the
   existing obligation registration/coordinator surface. Every write must use
   the existing append spine; no state scheduler or semantic truth owner.
3. [x] Add an `infra-survival-state-obligation` profile with one pytest call per
   asserted capability, then synchronize August analysis, formal dependency
   record, Harness docs and evidence.
4. [x] Run focused tests, predecessor continuation gate, the new profile,
   `python -m pytest -q`, and `git diff --check`.

Evidence: `.harness/verification/infra-survival-state-obligation-report.json`,
`.harness/verification/infra-continuation-gate-report.json`, and the fresh
2026-08-13 full suite (`2740 passed`).
