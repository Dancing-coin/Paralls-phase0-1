# INF-2E Activation-Released Dehydration Expiry Implementation Plan

Status: `implemented and verified 2026-08-14`

1. [x] Add failing focused tests for the dehydration pending/release row and
   independent success, duplicate, changed duplicate, revision, privacy,
   unregistered state, terminal, replay and receipt assertions.
2. [x] Extend the release merge only with a closed obligation-id-to-state map
   for `cold` and `dehydrated`; preserve all other zero-write fences.
3. [x] Reuse the existing `SurvivalAuthority` fragment and coordinator append
   path; do not add an activation-owned target write or cross-stream receipt.
4. [x] Add a dedicated Harness profile/report and synchronize status documents
   after evidence is green.
5. [x] Run predecessor profiles, focused tests, docs gate, diff check and the
   full suite.

Evidence: `.harness/verification/infra-activation-dehydration-expiry-report.json`.
