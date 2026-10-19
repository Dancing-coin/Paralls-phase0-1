# Durable cognition shared contract implementation

Goal: close the durable Siming portion of R06 using existing contracts and receipts.

Spec: [shared contract design](../specs/2026-10-20-durable-cognition-shared-contract-design.md).

- [x] RED: durable L2 context and L3 prepared plan share one turn/envelope/policy; provider-pending reopening does not recompile.
- [x] Add optional validated frozen pair to existing L2/L3 preparation; partial/foreign pair rejects before gateway invocation.
- [x] Compile from real profile-backed stable skill registry and current dynamic state before durable Siming L2. Freeze with existing context and propagate progress pins.
- [x] Reuse that context at L3 and execution; preserve legacy frozen-frame recovery and background `commands=[]` semantics.
- [x] Run bounded cognition/frame/recovery/candidate tests, smallest applicable Harness, export evidence and clean owned resources.
- [x] Update matrix with remaining direct/background/dialogue/recall and revision limitations; commit scoped changes.

Review focus: source equality, no model-derived increase to an already frozen envelope, no fresh compilation on pending replay, no actor/turn/policy splice, no new persistence or world authority.

Evidence: foundation staged isolation 9 passed; durable staged isolation 129 passed; backend-contract passed. Exact runs and limits are recorded in the unified acceptance matrix. Commits: `2d420aae`, `84f3e668`. R06 remains partial outside durable Siming.
