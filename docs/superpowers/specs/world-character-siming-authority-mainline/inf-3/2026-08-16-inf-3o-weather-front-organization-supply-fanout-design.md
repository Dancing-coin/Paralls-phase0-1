# INF-3O Weather-Front Organization Supply Fanout

Status: `implemented and independently verified as one fixed Organization owner fanout row; broader INF-3 remains incomplete`

## Purpose

INF-3I already proves one project-visible committed weather-front source can be
consumed by the existing `OrganizationAuthority` to append one existing
`gameplay.organization.commerce_commitment_accepted` event. INF-3O adds one
separately admitted fixed two-target fanout on the same existing owner and
event family. It is a new finite row, not a generic consumer registry, target
list, or settlement runtime.

## Fixed Owner Contract

| Field | Fixed value |
| --- | --- |
| source owner | existing `EcologyHazardAuthority` / `authority:ecology` |
| target owner | existing `OrganizationAuthority` / `actor_gameplay.organization_domain` |
| source event | committed project-visible `gameplay.ecology.weather_front.propagated` |
| target streams | existing `gameplay:organization:{organization_ref_a}` and `gameplay:organization:{organization_ref_b}` |
| target event family | existing `gameplay.organization.commerce_commitment_accepted` |
| arity | exactly two distinct existing `organization_ref` values, canonically ordered |
| write path | Ecology opaque pair admission -> two existing Organization owner fragments -> one existing `GameplayEventStore.append_batch()` path |
| projection/replay | existing `OrganizationAuthority.commerce_commitment_projection` plus full/checkpoint-tail reconstruction |
| receipt | only the one resulting `GameplayEventStore.append_batch()` result |
| privacy | project-visible source and target events only |
| revision | exact committed ecology event/stream/head pin plus both current organization stream heads |
| idempotency | source plus canonical two-organization pair; exact duplicate replays, changed reuse rejects |

The Organization owner writes both commitment events from one bounded
same-owner batch. This package does not split the fanout into separate append
calls, create a second writer, or widen the event family.

## Admission And Rejection

`EcologyHazardAuthority` may issue only an opaque admission bound to one
committed weather-front source and one canonical pair of organization refs.
`OrganizationAuthority` must revalidate source event identity, project
visibility, ecology stream revision/head, both target stream revisions,
governed catalog row, exact pair arity/distinctness, and idempotency before it
builds the two reused commitment fragments and appends once.

Forged/missing admission, malformed/one-target input, duplicate targets,
catalog mismatch, non-project privacy, stale ecology head, and stale target
organization head are all zero-write. No caller supplies a stream, event type,
arbitrary target list, pricing, payment, scheduler, retry, compensation, new
owner, new stream, or new truth store.

## Non-goals

This does not introduce arbitrary ecology fanout, generic organization
fanout APIs, a consumer registry, payment or pricing truth, a scheduler,
branch promotion, multi-hop propagation, or any second event store/runtime.
