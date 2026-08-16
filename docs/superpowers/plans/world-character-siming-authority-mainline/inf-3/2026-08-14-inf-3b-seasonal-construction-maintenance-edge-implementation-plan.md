# INF-3B Seasonal Construction Maintenance Edge Implementation Plan

Status: `implemented and verified 2026-08-14; one non-frost ecology process edge only`

1. [x] Add focused RED tests for the one seasonal-process source to existing
   Construction maintenance owner edge, including all zero-write fences.
2. [x] Add a closed ecology proposal/admission contract that pins the committed
   seasonal process event, stream revision, region, policy and privacy.
3. [x] Add Construction's source-aware maintenance fragment/settlement path;
   retain Construction as the only writer of its stream and include source
   provenance in its canonical event.
4. [x] Add independent Harness checks for success, rejection, idempotency,
   revision, privacy and replay; update August analysis and root dependency
   design/plan only after evidence is green.
5. [x] Run predecessor Harness, focused tests, docs, diff check and full suite.

Evidence: `.harness/verification/infra-seasonal-construction-maintenance-report.json`.

Non-goals: generic propagation, new scheduler/store/runtime, economy/body/social
truth, population effects, branch work, compensation/retry generalization, SOC,
GAME, P6 and P7.
