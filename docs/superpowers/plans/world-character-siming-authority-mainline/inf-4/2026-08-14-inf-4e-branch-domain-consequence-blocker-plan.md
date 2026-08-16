# INF-4E Branch-Domain Consequence Blocker Plan

Status: `blocked; no implementation authorized`

Date: `2026-08-14`

1. Keep `BranchPreviewAuthority` isolated and production-zero-write.
2. Preserve the dedicated branch evolution/disposition Harness reports and the
   explicit unsupported-promotion assertion.
3. Do not add a branch scheduler, event store, population/social truth owner,
   or production fragment execution path.
4. Resume only after an approved existing-owner branch evaluation contract
   supplies the target fragment semantics, branch record/reducer, privacy,
   revisions, idempotency and replay evidence requirements.
