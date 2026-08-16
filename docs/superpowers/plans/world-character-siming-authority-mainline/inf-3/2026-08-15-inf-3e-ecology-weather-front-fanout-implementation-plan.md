# INF-3E Ecology Weather-Front Fanout Plan

Status: `implemented and independently verified; bounded Ecology-only fanout`

1. [x] Confirm the existing Ecology owner, source/target streams, event family,
   append-derived receipt, projection and privacy boundary.
2. [x] Add focused RED tests for one three-target batch and independent
   projection/idempotency/revision/adjacency/privacy/replay checks.
3. [x] Add only a closed fanout policy, Ecology owner entrypoint and the
   event-derived full-edge projection; preserve the legacy latest frontier view.
4. [x] Add independent Harness evidence and synchronize formal/August docs.
5. [x] Run focused/dependent tests, gates, `git diff --check` and full pytest
   (`3059 passed`; only the existing `pytest_asyncio` deprecation warning).
