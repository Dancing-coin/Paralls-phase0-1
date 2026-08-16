# INF-1D Survival Effect Owner Matrix Implementation Plan

Status: `implemented and verified for the named closed Survival row`

Date: `2026-08-14`

1. Preserve the failing registration/bridge test for `effect:heat_exposure` to
   `state:overheated@1`.
2. Add the one exact matrix row to `SemanticRegistry`; do not loosen the
   lifecycle registration predicate.
3. Make the existing semantic-to-Survival bridge consume only the registered
   pair returned by that matrix, then reuse `SurvivalAuthority.apply_effect_state`.
4. Add lifecycle, rejection, privacy, idempotency and checkpoint-tail tests for
   the new row, a dedicated Harness profile/report, and synchronize the August
   and root status documents.
5. Run focused tests, profiles, `git diff --check`, then full pytest.

## Execution record

The initial registration test failed with
`semantic_lifecycle_owner_unregistered`. The implementation added only the
explicit `overheated` row and exact effect/state pairing. Its dedicated Harness
report has passed; final repository verification remains required for this turn.
