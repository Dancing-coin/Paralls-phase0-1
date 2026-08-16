# INF-1E Survival Dehydration Effect Owner Row Implementation Plan

Status: `implemented and verified 2026-08-14`

1. [x] Add focused failing tests for the exact dehydration row and all required
   success, idempotency, changed-input, revision, privacy, unmapped-pair,
   settlement/replay and outbox assertions.
2. [x] Extend only `SemanticRegistry`'s exact closed Survival pair and
   scheduled-lifecycle predicate. Do not loosen any owner/stream/event field.
3. [x] Reuse `SemanticSettlementAuthority.settle_closed_survival_state()` and
   `SurvivalAuthority.apply_effect_state()` unchanged as the sole write path.
4. [x] Add a dedicated Harness profile with one focused pytest assertion per
   capability and write its evidence report.
5. [x] After evidence is green, synchronize INF-1 README, root dependency
   spec/plan, August semantic analysis and `docs/harness.md`; run predecessor
   harnesses, focused tests, `git diff --check` and full pytest.

Non-goal: a generic StateDefinition registry, another effect owner, or a new
obligation lifecycle implementation.

Evidence: `.harness/verification/infra-survival-dehydration-state-obligation-report.json`.
