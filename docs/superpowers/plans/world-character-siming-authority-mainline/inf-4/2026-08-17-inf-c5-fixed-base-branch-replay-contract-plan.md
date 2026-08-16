# INF-C5 (INF-4) Fixed-Base Branch Replay Contract Plan

Status: `implemented and independently verified`

1. [x] Add focused RED tests with independent assertions for fixed base,
   calibration/source digest, canonical input ordering, cross-branch stream,
   projection replay and unsupported promotion.
2. [x] Implement the pure `FixedBaseBranchReplayContract` without append,
   owner selection, promotion or a second runtime/store.
3. [x] Integrate the contract into the existing `BranchPreviewAuthority`
   preview buffer, durable snapshot replay and fixed Organization supply
   admission; preserve owner-built production fragments.
4. [x] Add an independent Harness profile and report with one selector per
   capability.
5. [x] Synchronize INF-4 indexes, reusable-substrate status, the mapping guide,
   August analysis and the mainline completion audit.
6. [x] Run focused tests, existing branch/promotion regression, Harness,
   `git diff --check` and the full backend suite.

Verification completed on 2026-08-17: focused C5 tests (8 passed), existing
branch/promotion regression (43 passed), independent Harness (9 selectors
passed), final diff check, and the full backend suite (3471 passed).
