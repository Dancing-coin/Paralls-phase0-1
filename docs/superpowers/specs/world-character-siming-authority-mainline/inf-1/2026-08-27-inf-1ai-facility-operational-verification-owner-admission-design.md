# INF-1AI Facility Operational Verification Owner-Admission Contract

Status: `implemented narrow vertical; August INF A-D remain not complete`

## Product Loop

```text
committed Construction run_finished@1 with completed ProductionRun
-> existing ConstructionProductionAuthority
-> one Construction-owned facility_operationally_verified@1 projection fact
```

This gives the construction owner a durable, replayable answer to “has this
facility completed a real production run?” It does not duplicate Production
completion truth and does not imply output custody, maintenance clearance,
permit, technology, material, payment, inventory, weather, social or population
facts.

## Exact Contract

| Field | Fixed rule |
| --- | --- |
| capability / outcome | `capability:construction-facility-operational-verification@1` / `outcome:construction-facility-operationally-verified@1` |
| descriptor / catalog | `descriptor:construction-facility-operational-verification@1`; `inf:construction-facility-operational-verification@1`, kind `lifecycle` |
| owner | existing `ConstructionProductionAuthority` (`actor_gameplay.construction_production_domain`) |
| source | one committed project-visible `gameplay.construction_production.run_finished@1` for a run whose projected status is `completed`, plus its same-facility `run_started@1` provenance and current facility projection |
| source pins | run-start event id/revision, run-finished event id/revision, run ref, facility ref, recipe ref, current Construction facility revision and target stream head; source event and target are project-visible |
| eligibility | `construction:production-run-completed@1`; predicate `predicate:construction-production-run-completed@1`; proof binds `run_ref`, `facility_ref`, `project_ref=facility.plot_ref`, exact run-start/run-finished revisions, and current facility revision |
| target stream / event | `gameplay:construction_production:{facility_ref}`; exactly `gameplay.construction_production.facility_operationally_verified@1` |
| target payload | fixed facility/run refs, project binding, source event ids/revisions, prior/current facility revision, `verification_status=operationally_verified`, descriptor/catalog/policy pins; caller selects none |
| policy | `policy:construction-facility-operational-verification@1` |
| privacy | project-scoped for source, target, receipt and replay |
| idempotency | `construction:facility-operational-verification:{run_finished_event_id}:{run_finished_revision}:{facility_revision}:{target_stream_head}:v1`, derived by Construction owner |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; Construction projector full/checkpoint-tail replay must produce the same verification record and source vector |
| package | `not_applicable`; this row is a fixed existing-owner operation and does not freeze or mutate any gameplay package |
| lifecycle | v1 terminal one verification per run/facility revision; no reversal, downgrade, retry-as-new, compensation, fanout, payment, material or output semantics |

## Conflict-Matrix Preflight

Disposition: `new`.

Production retains `run_finished` and output/completion truth. Construction owns
the separate facility-level operational verification projection. Existing
`work_completion_evidence_recorded` is actor-scoped worker evidence and is not
reused as a facility fact. Existing maintenance, repair, transform and
decommission rows claim different facts and lifecycle transitions.

Rejected alternatives:

- Reclassify `run_finished` as facility verification: rejected because it would
  overload Production truth and remove the Construction-owned projection.
- Use worker completion evidence: rejected because it is actor-scoped and may
  describe a contribution, not facility operation.
- Emit inventory/payment/permit effects: rejected because those facts belong to
  separate owners and are not needed for this feedback loop.

## Required Zero-Write

Reject before append for unknown/private/wrong-stream/wrong-kind source;
missing or non-completed run; missing run-start provenance; run/facility/project
binding conflict; stale source/facility/target revision; decommissioned or
missing facility; multiple matching run-finished events; existing verification;
catalog/descriptor mismatch; duplicate or changed duplicate; caller-selected
owner/stream/event/privacy/revision/receipt; and any request containing
payment/material/output/maintenance or cross-domain fragments.

## Implementation Boundary

Add one strict Construction intent, one fixed projector branch and one owner
method. Extend only the existing Construction projection and immutable catalog
tuples. Build one project-scoped event through
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
No package, registry, router, generic transform, new owner, or second runtime is
introduced.

## Implementation Evidence

The focused INF-1AI tests, immutable Construction catalog/descriptor regression,
independent `infra-construction-facility-operational-verification` Harness,
continuation gate, and complete INF-focused suite pass. The event is project
visible, append-derived, idempotent, and full/checkpoint-tail replayable. It
does not alter the Production run, output, facility kind, maintenance, or any
other domain fact.
