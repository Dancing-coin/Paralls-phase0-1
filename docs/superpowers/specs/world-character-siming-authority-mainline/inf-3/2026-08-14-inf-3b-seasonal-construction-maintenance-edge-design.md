# INF-3B Seasonal Construction Maintenance Edge Design

Status: `implemented and verified for one non-frost seasonal process -> Construction maintenance edge; broader INF-3 propagation remains incomplete`

## Scope

This is exactly one non-frost ecology consumer edge:

```text
committed project-visible ecology seasonal_process_advanced
-> EcologyHazardAuthority proposal/admission
-> ConstructionProductionAuthority source-aware maintenance fragment
-> GameplayEventStore.append_batch() on the existing construction stream
```

The source authority remains `authority:ecology` on
`gameplay:ecology:{region_ref}`. The target authority remains
`actor_gameplay.construction_production_domain` on
`gameplay:construction_production:{facility_ref}`. No ecology method may append
to the construction stream.

## Source pins and admission

The ecology proposal pins the exact committed `seasonal_process_advanced` event
id, ecology stream revision, region ref, process policy ref/revision, elapsed
ticks, and project visibility. It may be proposed only from the latest active
project-visible process event for that region. Retired/missing/private/stale or
forged source state is a zero-write rejection.

The admission object is opaque and issued only through the construction-owned
closure, following the existing frost edge pattern. The new edge ref is
`ecology-process:seasonal-to-construction-maintenance:v1`. It must not be
constructed by a client, LLM, creator, Siming, or direct target call.

## Target contract

Construction accepts the admitted command only when the edge ref, admission
identity, source authority, source stream revision, process event id, region
ref, and project privacy all match current source facts. The target caller
supplies an existing `ProductionRun`; Construction validates the expected head
of `gameplay:construction_production:{facility_ref}` and writes only:

`gameplay.construction_production.maintenance_obligation_created`

Its event carries immutable `seasonal_ecology_propagation` provenance with the
source event/ref/vector and edge ref. The target event is idempotent on the
existing construction principal and command key, receives the normal outbox and
replays through existing scoped projections. It creates no generic ecology
propagation engine, scheduler, obligation store, or construction truth owner.

## Verified proof

Focused tests and the independent `infra-seasonal-construction-maintenance`
Harness profile separately prove:
success; direct/forged admission zero-write; missing/stale/private source
zero-write; target revision conflict; duplicate idempotency; target scoped
privacy; and full/checkpoint-tail replay. This edge does not complete broad
hazard fanout, multi-region process scheduling, economy/body/social effects,
or generic compensation/retry.

Evidence: `.harness/verification/infra-seasonal-construction-maintenance-report.json`.
