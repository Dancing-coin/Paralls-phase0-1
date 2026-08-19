# INF-1AE Construction Action Owner-Contract Audit

Status: `implemented narrow vertical; verified 2026-08-17`

## Row

The next INF-1 lifecycle row was narrowed to one Construction facility repair
outcome. The existing Construction authority owns the facility stream, and the
approved contract now names one repair event and one explicit compensation
event. Transform, payment, and other action inputs remain unsupported.

| Contract field | Evidence | Disposition |
| --- | --- | --- |
| owner and append path | `ConstructionProductionAuthority` owns the facility stream through the existing store | verified |
| event family and revision | `facility_repaired` and `facility_repair_compensated`, schema version 1, facility revision pin | verified |
| privacy and idempotency | project scope, owner principal, expected stream revision, changed-duplicate zero-write | verified |
| receipt, replay, compensation | append receipt, scoped outbox, projector full/checkpoint-tail replay, latest-repair compensation | verified |

The implementation uses `GameplayCommandEnvelope -> SettlementPlan ->
GameplayEventStore.append_batch()` and leaves all unlisted Construction
actions at the existing zero-write boundary.

Evidence: `backend/tests/test_infra_construction_facility_repair.py` (9
focused tests) and `infra-construction-facility-repair` prove success,
zero-write rejection, privacy, revision, idempotency, receipt, compensation,
full replay, and checkpoint-tail replay.

## Remaining boundary

This does not admit Construction transform, payment, material, service
completion, or generic action routing. Those remain owner-contract blocked or
unimplemented until a separate exact contract exists.

## Rejected near-miss authorities

`StateGroupLifecycleAuthorityService` and `StatusTagAuthorityService` were
checked as possible existing writers. They own separate Gameplay foundation
event families (`gameplay.state_group.*` and `gameplay.status_tag.*`) and their
own projections; neither publishes an INF semantic effect/state owner row,
Construction target stream, or the required INF receipt/replay/compensation
binding. Treating either as the missing Construction authority would create an
unapproved cross-domain owner substitution, so both remain out of scope.
