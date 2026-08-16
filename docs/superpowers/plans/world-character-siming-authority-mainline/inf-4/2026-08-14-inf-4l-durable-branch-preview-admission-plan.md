# INF-4L Durable Branch Preview Admission Evidence Plan

Status: `implemented and verified`

1. [x] Add focused failing tests proving the current primitive/proposal inputs
   cannot be used as accepted-preview provenance, and specifying the durable
   evidence-to-Government path for both passed and failed inspection rows.
2. [x] Extend only the existing `BranchPreviewAuthority` with one
   `creator_debug` proposal-evidence append on `gameplay:branch_preview:{branch_ref}`
   through the existing command/SettlementPlan/event-store spine.
3. [x] Change only `GovernmentAuthority` scenario settlement to consume and
   revalidate the durable evidence event; derive all scenario fields internally
   and retain its existing non-production stream/outbox/projection.
4. [x] Add a dedicated Harness with independent evidence, consequence,
   rejection, idempotency, privacy and replay selectors; rerun INF-4I, INF-4J
   and then INF-4K as explicit predecessors.
5. [x] Revalidated 2026-08-14 after the exact evidence-stream identity repair:
   passed and failed cross-branch forged admissions are independent zero-write
   Harness assertions. The root dependency record, August analysis and Harness
   continue to describe this as a narrow evidence/provenance repair, not generic
   receipt or branch settlement. `git diff --check`, the focused suites, INF-4L,
   INF-4J and INF-4K Harnesses passed; broad pytest remains a final mainline gate.
