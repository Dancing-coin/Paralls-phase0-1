# INF-1K Semantic Survival State Action Lifecycle Plan

Status: `implemented and verified; closed Survival-only rows`

1. [x] Add focused RED tests for the exact dispel and recovery-transform rows,
   including zero-write, duplicate, revision, privacy, outbox and replay cases.
2. [x] Add closed registry action routes and a typed proposal. Do not expose a
   caller-selected state/replacement/action router.
3. [x] Delegate only to existing `SurvivalAuthority` fragments through the
   existing `policy:survival_state_expiry@1` coordinator and append path.
4. [x] Add a dedicated Harness profile with one independent assertion for each
   claimed capability.
5. [x] Run focused tests, profile, docs/continuation gates, `git diff --check`
   and full pytest; synchronize all formal status surfaces after review.

The verified profile has fifteen isolated assertions. Its append idempotency
digest includes the full typed semantic action command, so changed snapshot
evidence with a reused key remains a zero-write rejection.
