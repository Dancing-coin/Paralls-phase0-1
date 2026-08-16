# INF-3P C4 Economy and Survival Consumer Adoption Plan

Status: `completed; focused tests and independent Harness verified`

1. Add focused tests proving each existing Economy and Survival weather row
   invokes C4 before owner fragment construction; C4 rejection must be
   zero-write. Run them red before production edits.
2. Import and invoke the existing read-only C4 check in the four owner methods,
   passing the fixed catalog contract, source pin, target revisions and
   idempotency key. Preserve each method's opaque Ecology admission.
3. Prove success, C4 rejection zero-write, duplicate idempotency, revision,
   privacy, full replay and checkpoint-tail replay with independent Harness
   selectors. Existing focused row tests remain the detailed source evidence.
4. Synchronize INF-3 spec/plan indexes, August analysis, mainline audit and
   dedicated Harness evidence. Do not call this generic consumer expansion.

Completion evidence: focused package suite `44 passed`; independent Harness
profile `infra-ecology-c4-economy-survival-adoption` has 14 selectors and
report `infra-ecology-c4-economy-survival-adoption-report.json` with all
selectors passing. Formal writes remain existing Economy/Survival owner
fragments through the single `GameplayEventStore.append_batch()` path;
replay, privacy, revision, idempotency and zero-write rejection are covered.
