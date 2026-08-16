# INF-4O Organization Supply Promotion Plan

Status: `implemented and independently verified`

1. Add RED tests for the fixed Organization-owned supply promotion contract and
   every zero-write boundary. Complete.
2. Add `OrganizationAuthority` validation and a fixed production commerce
   fragment using `GameplayCommandEnvelope` / `SettlementPlan` and the existing
   `GameplayEventStore.append_batch()` path. Complete.
3. Return an append-derived `OrganizationBranchPromotionReceipt`; do not add a
   generic branch writer or promotion coordinator. Complete.
4. Add an independent Harness verifier/profile, sync INF-4 and remaining-scope
   docs, then run focused tests, replay/privacy checks, docs check, diff check,
   and the full pytest suite. Harness complete; repository-wide verification is
   the final package closeout step.
