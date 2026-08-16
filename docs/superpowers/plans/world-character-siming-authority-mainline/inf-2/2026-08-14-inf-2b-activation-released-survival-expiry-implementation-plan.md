# INF-2B Activation-Released Survival Expiry Implementation Plan

Status: `implemented and verified 2026-08-14; one two-receipt owner row only`

1. [x] Add RED focused tests for a released, event-derived
   `survival_state_expiry` pending row: success, duplicate idempotency,
   revision conflict, privacy, forged/terminal zero-write, and checkpoint-tail
   replay.
2. [x] Extend only `ProfileActivationAuthority`'s admitted pending schema and
   its event-derived projection; extend only the existing Survival/coordinator
   settlement surface. Do not add a scheduler, store, bus, clock, owner or
   multi-stream receipt.
3. [x] Register a dedicated Harness profile with one selector per capability;
   run predecessor, focused, replay, docs, full pytest and `git diff --check`.
4. [x] Synchronize August analysis, dependency design, plan and evidence with
   the exact two independent append receipts and remaining generic gaps.
