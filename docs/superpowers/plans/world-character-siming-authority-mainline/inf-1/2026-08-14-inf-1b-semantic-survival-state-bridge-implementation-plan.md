# INF-1B Semantic Survival State Bridge Implementation Plan

Status: `implemented and verified 2026-08-14; two closed Survival owner rows only`

1. [x] Record the only legal mappings: `authority:semantic` proposal to existing
   `SurvivalAuthority` for `effect:cold_exposure` / `state:cold@1` and
   `effect:heat_exposure` / `state:overheated@1` on
   `gameplay:survival:{actor_ref}`.
2. [x] Add RED focused coverage for proposal-to-owner submission, then implement
   a closed bridge that delegates to `SurvivalAuthority.apply_effect_state()`.
3. [x] Add independent focused assertions for success, duplicate idempotency,
   revision zero-write, privacy/unmapped-owner zero-write and checkpoint-tail
   replay.
4. [x] Register `infra-semantic-survival-state-bridge`; synchronize formal,
   August and Harness documentation. Do not claim generic lifecycle closure.
