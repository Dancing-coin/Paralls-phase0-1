# INF-1O State Action Lifecycle Closure Plan

Status: `implemented and verified 2026-08-15; bounded Survival action closure only`

1. [x] Name the existing Survival owner rows, stream, action event family,
   privacy, revision and receipt boundary in the formal design.
2. [x] Add focused RED tests for pure apply/dispel/transform decisions and the
   existing Survival owner settlement, including rejection, idempotency,
   revision/privacy zero-write and replay.
3. [x] Extend only `StateDefinition`, `EffectLifecycleEvaluator`, and the
   existing `SurvivalAuthority`/semantic action path; no generic writer.
4. [x] Add an independent Harness profile/report and synchronize INF-1 trees,
   root dependency records, and August analysis.
5. [x] Run focused/dependent tests and the independent Harness, then verify
   docs gate, continuation gate, `git diff --check`, and full suite
   (`3044 passed`; only the existing `pytest_asyncio` deprecation warning).

Do not admit any owner/action pair outside the fixed Survival matrix.
