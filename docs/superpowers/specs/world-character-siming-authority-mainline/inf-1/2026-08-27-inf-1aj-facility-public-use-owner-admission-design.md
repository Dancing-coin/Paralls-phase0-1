# INF-1AJ Construction Facility Public-Use Enablement Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic facility availability remains blocked`

## Exact Row

```text
committed Construction facility_operationally_verified@1
  (facility_kind = oven, project-visible, current and active)
-> existing ConstructionProductionAuthority
-> one facility_public_use_enabled@1 fact
```

This is a product-facing readiness fact for the town's public-place loop: an
oven that has completed a real production run is marked usable by the
Construction projection. It changes only the Construction-owned
`public_use_status` and facility revision. It does not create production
output, inventory, material, payment, permit, technology, weather,
maintenance, social, population, or generic facility-transform facts.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:construction-facility-public-use-enable@1` / `outcome:construction-facility-public-use-enabled@1` |
| owner | existing `ConstructionProductionAuthority` (`actor_gameplay.construction_production_domain`) |
| source | exactly one committed project-visible `gameplay.construction_production.facility_operationally_verified` event for the same facility; its source run-start/run-finished vector, facility/project binding and current stream head are pinned |
| source predicate | `predicate:construction-facility-operationally-verified@1`; only `facility_kind=oven` and a non-decommissioned current facility qualify |
| target stream / event | `gameplay:construction_production:{facility_ref}` / `gameplay.construction_production.facility_public_use_enabled@1` |
| privacy | project-scoped; the event and projection are visible only through the existing project Construction boundary |
| subject | committed `facility_ref` and `project_ref=facility.plot_ref`; caller cannot select target coordinates or kind |
| idempotency | owner-derived `construction:facility-public-use-enable:{verification_event_id}:{verification_revision}:{facility_revision}:{stream_head}:v1` |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; existing Construction projector supports full/checkpoint-tail replay |
| fixed payload | facility/project refs, `facility_kind=oven`, `prior_public_use_status=unavailable`, `next_public_use_status=enabled`, source verification event/revision, source run-start/run-finished refs/revisions, prior and next facility revision, expected stream revision, policy and descriptor pins |
| lifecycle | v1 terminal; no disable, re-enable, reversal, compensation, retry-as-new, fanout or cross-domain effect |

`unavailable` is the Construction projection's pre-admission status, not a
claim that the facility is unsafe or unlicensed. No public-use state is
inferred for facilities without this exact event.

## Zero-Write Rules

Unknown/missing/private/non-project verification, wrong event or source
revision, wrong facility kind, decommissioned or missing facility, mismatched
project/facility binding, missing source run vector, stale verification or
facility stream head, current public-use status already enabled, catalog or
descriptor mismatch, duplicate or changed duplicate, and caller-selected
owner/stream/event/privacy/revision/receipt are rejected before append.

The exact duplicate replays the original owner receipt. A changed request under
the same derived key is zero-write. No event is emitted for `mill`,
`mill_reinforced`, `kiln`, bakery, or any future kind through this capability.

## Conflict Matrix

Disposition: `new` existing-row Construction extension. INF-1AI owns the
operational-verification evidence; INF-1AJ owns the separate public-use
projection status. Existing repair, transform, decommission, maintenance,
work-history and production-output partitions are not reused. No new owner,
generic transform, router, registry, coordinator, writer, settlement
authority, or second runtime is introduced.
