# INF-2L Debt Settlement Formal Spine Plan

Status: `implemented bounded and verified 2026-08-16; owner-local replay reader closure backfilled`

1. [x] Add RED tests that distinguish the formal plan/fragments/read-vector/outbox
   path from the former raw batch append.
2. [x] Introduce closed typed debt event specs and `DebtSettlementPlan`; migrate
   the existing append adapter without changing simple-debt domain semantics.
3. [x] Preserve duplicate, rejection and replay behavior; add a redacted
   authority-scoped outbox only.
4. [x] Add a dedicated Harness profile/report, sync INF-2 and August docs, then
   run focused, predecessor, docs, diff and full-suite verification.

Closure evidence: `infra-debt-settlement-formal-spine` carries ten independent
selectors, including issue/payment formal-path and legacy-compatibility proof.
The backfilled `DebtAuthorityService.replay_projection` reader is separately
checked against full and checkpoint-tail replay and against the catalog metadata.
It is a fixed simple-debt migration, not admission of caller-open policy
registration, arbitrary payment, or generic cross-domain settlement.
