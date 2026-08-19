# INF-1P Construction Maintenance State-Action Admission Audit Plan

Status: `implemented bounded Construction dispel and verified; transform stopped at owner-contract gate`

1. Re-run the relevant continuation, Construction maintenance lifecycle and
   Survival action reports before reviewing the candidate row.
2. Inspect the Construction authority, stream events, projector and receipt
   path for a repair/clear/dispel/transform action contract.
3. Write RED tests for the exact bounded dispel: one Construction action event
   plus one cancellation event in a single owner batch, with idempotency,
   stale revision, privacy, unsupported transform and full/checkpoint-tail
   replay assertions.
4. Add only the fixed `effect:maintenance_state_dispel` route, the matching
   Construction owner fragment, lifecycle registration and projector handling.
5. Keep generic repair, payment, material semantics and transform inputs
   zero-write; INF-1AE owns only one explicit facility repair pair.
   they lack a replacement-state truth contract.
6. Add a dedicated Harness profile/report and synchronize the INF-1 tree,
   root formal documents and August analysis.

Result: all steps complete. The focused suite, ten-selector Harness report,
documentation gate, `git diff --check` and full backend suite passed. The
generic transform/repair/payment/material boundary remains blocked and
zero-write.
