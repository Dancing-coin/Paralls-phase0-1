# INF-1AC Weather-front Survival Cold Owner Row Plan

Status: `implemented and independently verified`

1. [x] Add independent RED selectors for success, forged/private/mismatched
   evidence zero-write, inactive profile zero-write, exact duplicate,
   changed-idempotency zero-write, Survival/Ecology/population revision fences,
   privacy and full/checkpoint-tail replay.
2. [x] Add one exact governed owner-contract catalog row and extend only the
   existing `SurvivalAuthority` with a source-revalidating cold-exposure entry.
3. [x] Keep formal writes on `GameplayCommandEnvelope -> owner fragment ->
   GameplayEventStore.append_batch()` and make the append result the only
   receipt boundary.
4. [x] Add a dedicated Harness profile, verifier and evidence report whose
   checks invoke separate focused selectors.
5. [x] Sync INF-1/INF-3/INF-4 indexes, August analysis, mainline audit and
   dependency spec/plan without claiming generic weather or Survival support.
6. [x] Run focused tests, Harness, `git diff --check`, and `python -m pytest -q`.
