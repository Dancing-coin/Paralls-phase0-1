# INF-3D Ecology Weather-Front Path Propagation Plan

Status: `implemented and independently verified; bounded Ecology-only path`

1. [x] Name the existing Ecology owner, streams, event family, projection,
   privacy, revision, idempotency, replay, and append-derived receipt boundary.
2. [x] Add focused RED tests for one three-hop path and each independent
   rejection/visibility/replay capability.
3. [x] Add only a closed path policy and an `EcologyHazardAuthority` entrypoint
   that merges one owner fragment per existing path stream into one append.
4. [x] Add an independent Harness profile/report and synchronize INF-3 trees,
   root records, and August analysis.
5. [x] Run focused/dependent tests, continuation review, docs check,
   `git diff --check`, and the full suite (`3052 passed`; only the existing
   `pytest_asyncio` deprecation warning).

The existing two cross-domain ecology consumer edges stay unchanged. No path
may manufacture a third edge or append outside `gameplay:ecology:{region_ref}`.
