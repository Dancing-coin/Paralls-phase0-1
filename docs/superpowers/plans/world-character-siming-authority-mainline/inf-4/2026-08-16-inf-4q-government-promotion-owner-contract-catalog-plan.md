# INF-4Q Government Promotion Owner-Contract Catalog Plan

Status: `implemented and independently verified for the fixed Government passed-inspection promotion row; broader INF-4 remains incomplete`

1. Confirm INF-4N's existing Government owner, source admission/scenario,
   production stream, event family, project projection, append-derived receipt
   and full/checkpoint-tail replay evidence. `completed`
2. Add a focused failing test that makes the immutable catalog reject the
   Government promotion operation and proves the production stream stays at
   revision zero. `completed`
3. Add one source-controlled catalog row and require it immediately before the
   existing Government fragment/append path. `completed`
4. Add a profile/report with separate metadata, pre-append zero-write,
   duplicate, revision, privacy and replay assertions. `completed`
5. Synchronize INF-4, remaining-scope, August analysis and Harness indexes;
   rerun predecessors, focused tests, replay evidence, `git diff --check` and
   full pytest. `completed`

Non-goals: dynamic registration, generic promotion, generalized receipt,
promotion of other owner rows, production writeback from `BranchPreviewAuthority`,
and complete group simulation.
