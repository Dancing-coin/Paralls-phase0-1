# INF-1AD Weather-front Survival Overheated Plan

Status: `implemented and independently verified as one exact existing-owner source edge`

1. [x] Write focused RED tests for success, wrong source, forged source,
   privacy, revision, idempotency, changed duplicate, outbox and replay.
2. [x] Add the immutable governed catalog row for the existing Survival owner.
3. [x] Route `weather:heat` evidence through `SurvivalAuthority` and its
   existing `GameplayEventStore.append_batch()` state/obligation path.
4. [x] Add an independent Harness profile/report with one selector per check.
5. [x] Synchronize INF-1 indexes, mainline audit and August status.
6. [x] Run focused tests (25 passed), the 12-selector package Harness,
   `git diff --check` and the full backend suite (3471 passed).

The package remains a narrow edge. Generic effect/state routing, arbitrary
weather consumers, fanout and additional owner contracts remain blocked.
