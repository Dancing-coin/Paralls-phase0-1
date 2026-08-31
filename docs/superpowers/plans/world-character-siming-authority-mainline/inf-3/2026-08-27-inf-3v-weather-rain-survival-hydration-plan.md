# INF-3V Weather Rain Survival Hydration Implementation Plan

Status: `implemented and verified; Goal active; August INF A-D not complete`

1. [x] Write RED tests for the exact rain weather-front and active region
   assignment source.
2. [x] Add only the immutable Survival consumer catalog/descriptor row.
3. [x] Implement the strict Survival source verifier and fixed state/obligation
   append vector through the existing envelope/SettlementPlan spine.
4. [x] Add independent Harness and verify privacy, revisions, idempotency,
   receipt, full/tail replay, expiry and zero-write boundaries.
5. [x] Synchronize audit, remaining-scope, README, taxonomy, matrix, and
   checkpoint; run INF/full regression suites.

This row is rain-only and hydration-only. `drought_process_advanced` is never a
source, and no generic weather consumer or fanout route is added.
