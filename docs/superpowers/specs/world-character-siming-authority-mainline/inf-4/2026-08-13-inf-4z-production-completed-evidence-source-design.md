# INF-4Z Production Completed-Evidence Source Admission

Status: `implemented and verified narrow source package; no wage consumer admitted`

## Scope

This package admits only `production-completed` evidence for a prior committed
production run. It is the missing source contract for a later work-to-wage
consumer row. It does not admit the wage row, actor-declared completion,
procurement/service evidence, payroll payment, population truth, scheduling,
P6, or P7.

## Owner matrix

| Element | Contract |
| --- | --- |
| Owner | existing `ConstructionProductionAuthority` / `actor_gameplay.construction_production_domain` |
| Stream | existing `gameplay:construction_production:{facility_ref}` |
| Start linkage | existing `run_started` event gains only immutable `worker_contribution_refs`; each row contains `actor_ref`, `assignment_ref`, `work_order_ref`, and opaque `contribution_digest` |
| Evidence event | `gameplay.construction_production.work_completion_evidence_recorded` on the same production stream, emitted only by `ConstructionProductionAuthority` after the corresponding committed `run_finished` event |
| Required evidence payload | Production derives the canonical evidence ref from committed `run_ref + contribution_digest`; payload records run/facility/worker/assignment/work-order refs, `production-completed`, verified completed state, source digest, source run-finished event ref and revision |
| Scoped reader | revisioned `ProductionCompletedEvidenceView`: the matching worker and `actor_gameplay.construction_production_domain` may read rows; public/other actors receive no rows |
| Write path | typed authority call -> `GameplayCommandEnvelope` / `SettlementPlan` -> `GameplayEventStore.append_batch()` -> production outbox/replay -> scoped projection |
| Future consumer | frozen view only; it must later pin digest, event refs and stream revision before the existing economy wage fragment is eligible |

The production authority validates the source run linkage against its own
projector. The worker contribution must be committed on `run_started`; a raw
`finish_work` request, empty or actor-declared evidence ref, mismatched
worker/work-order, stale run stream, or duplicate with changed payload has zero
writes. This API contains no caller-supplied verification state: verified
completion is derived only from the committed `run_finished` source. Corrections
are future production owner events; no compensation is introduced.

## Privacy and replay

The production event uses `actor:{worker_ref}` scope for the worker. Its outbox projection
contains only run/evidence references; no recipe inputs, inventory, body state,
or wage detail is exposed. Full and checkpoint-tail replay reproduce the same
evidence view digest and source vector.

## Completion evidence

Focused tests independently cover owner/stream/event, committed-source
requirement, canonical-envelope/SettlementPlan append path, actor event scope,
outbox redaction, empty/untrusted/mismatched/stale zero-write, duplicate and
changed duplicate, worker/authority/other-reader scope, and full/checkpoint-tail
replay plus view digest/vector reconstruction. The separate
`infra-production-completed-evidence-source` Harness profile proves every
capability with its own pytest invocation. Only a later, separately designed
consumer package may consider the existing Economy wage fragment.
