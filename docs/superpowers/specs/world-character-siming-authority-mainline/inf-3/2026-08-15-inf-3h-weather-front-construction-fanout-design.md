# INF-3H Weather-Front Construction Consumer Fanout

Status: `implemented and independently verified; fixed two-facility Construction fanout`

INF-3H admits one fixed two-facility consumer fanout on the existing
`ConstructionProductionAuthority`. Ecology proposes only an opaque admission
for one project-visible `weather_front.propagated` source event and exactly two
existing facility refs. Construction validates the source and every target
stream revision, then writes one existing
`gameplay.construction_production.maintenance_obligation_created` event per
facility through one `GameplayEventStore.append_batch()`.

The fanout is bounded and same-owner: it is not a generic consumer registry,
arbitrary target list, Economy/Organization writer, scheduler, retry/compensation
engine, or branch promotion path. Missing/forged admission, stale source or
target revisions, private source and changed idempotency are zero-write; exact
duplicates replay and both target projections remain project-scoped.
