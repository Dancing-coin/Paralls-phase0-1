# Durable cognition shared contract implementation

Goal: close the durable Siming portion of R06 using existing contracts and receipts.

Spec: [shared contract design](../specs/2026-10-20-durable-cognition-shared-contract-design.md).

- [ ] RED: durable L2 context and L3 prepared plan share one turn/envelope/policy; provider-pending reopening does not recompile.
- [ ] Add optional validated frozen pair to existing L2/L3 preparation; partial/foreign pair rejects before gateway invocation.
- [ ] Compile from real profile-backed stable skill registry and current dynamic state before durable Siming L2. Freeze with existing context and propagate progress pins.
- [ ] Reuse that context at L3 and execution; preserve legacy frozen-frame recovery and background `commands=[]` semantics.
- [ ] Run bounded cognition/frame/recovery/candidate tests, smallest applicable Harness, export evidence and clean owned resources.
- [ ] Update matrix with remaining direct/background/dialogue/recall and revision limitations; commit scoped changes.

Review focus: source equality, no model-derived increase to an already frozen envelope, no fresh compilation on pending replay, no actor/turn/policy splice, no new persistence or world authority.
