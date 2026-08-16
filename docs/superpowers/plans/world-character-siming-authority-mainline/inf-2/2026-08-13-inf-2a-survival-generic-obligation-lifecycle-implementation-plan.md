# INF-2A Survival Generic Obligation Lifecycle Implementation Plan

Status: `implemented bounded; do not claim INF-2 closure`

1. [x] Add focused failing tests for the event-derived lifecycle projection and
   status compatibility: construction plus Survival, due/catch-up ordering,
   registered versus forged open sources, and all newly enabled transitions.
2. [x] Extend the existing shared contract, coordinator registration and
   event-derived projection only. Preserve one clock, one coordinator and one
   `GameplayEventStore.append_batch()` receipt path.
3. [x] Add Survival owner fragments only for lifecycle transitions backed by
   explicit event families; registered retry and compensation now require
   event-derived source/terminal facts and explicit restore input.
4. [x] Add an independent Harness profile with one pytest invocation per
   capability; update August analysis, formal documents and evidence.
5. [~] The focused tests and independent profile were rerun after the final
   retry revision-conflict case. Re-run predecessor reports, full replay/
   checkpoint-tail, docs check, `python -m pytest -q`, and `git diff --check`
   before marking this package checkpoint-verified.

Evidence: `backend/tests/test_infra_generic_obligation_lifecycle.py` and
`.harness/verification/infra-generic-obligation-lifecycle-report.json`.
Implemented: two-owner event-derived view, canonical status parsing, registered
bounded Survival retry and settled-only compensation. Missing: an explicit
owner-side activation-lock pending/release mapping and final full-suite
checkpoint. Economy and every unregistered owner remain zero-write rejected.

Blocked activation mapping: `ProfileActivationAuthority` has a replayable
pending payload only for INF-4C's released `schedule_gated_supply` row, and no
`OwnerAuthorizedFragment` mapping for Survival obligations. Do not add
clock-side queue state or a coordinator writer.
