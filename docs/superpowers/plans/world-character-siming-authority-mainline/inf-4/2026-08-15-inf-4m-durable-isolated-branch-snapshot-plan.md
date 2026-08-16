# INF-4M Durable Isolated Branch Snapshot Plan

Status: `implemented and verified`

1. [x] Add RED focused tests for explicit snapshot append, idempotency,
   revision/privacy/missing-buffer zero writes, fresh-instance reconstruction,
   redaction, checkpoint-tail replay and unsupported promotion.
2. [x] Extend only existing `BranchPreviewAuthority` with a creator-debug
   snapshot command on its existing branch-preview stream.
3. [x] Add one independent Harness selector per admitted capability and retain
   separate zero-write selectors.
4. [x] Synchronize INF-4, the root dependency record, August analysis and the
   evidence report; run focused, predecessor, replay and full-suite checks.
