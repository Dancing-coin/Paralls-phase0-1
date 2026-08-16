# INF-1C1 Reusable State Transition Plan Implementation Plan

Status: `implemented and independently verified as a pure reusable proposal layer; broader INF-1 remains incomplete`

1. [x] Add RED tests for the pure plan shape and all four stack decisions.
2. [x] Add typed apply/dispel/transform plans while preserving existing
   `EffectLifecycleEvaluator.resolve*()` compatibility.
3. [x] Verify the same plan shape against existing Survival, Construction and
   Ecology registry definitions, plus compile and semantic regression tests.
4. [x] Add an independent Harness profile/report and sync INF/mainline docs.

No owner writer, registration API, scheduler, or second event store is added.
