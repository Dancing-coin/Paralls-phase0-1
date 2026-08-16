# INF-3N Weather-Front Economy Quote Fanout

Status: `implemented and independently verified as one fixed Economy owner fanout row; broader INF-3 remains incomplete`

## Purpose

INF-3J already proves one project-visible committed weather-front source can
be consumed by the existing `EconomyAuthorityService` to publish one existing
dynamic quote. INF-3N adds one separately admitted fixed two-quote fanout on
the same existing Economy owner, stream, event family, projection and receipt
spine. It is a new finite row, not a generic consumer registry or fanout API.

## Fixed Owner Contract

| Field | Fixed value |
| --- | --- |
| source owner | existing `EcologyHazardAuthority` / `authority:ecology` |
| target owner | existing `EconomyAuthorityService` / `actor_gameplay.economy_domain` |
| source event | committed project-visible `gameplay.ecology.weather_front.propagated` |
| target stream | existing `gameplay:economy` |
| target event family | existing `gameplay.economy.dynamic_quote_published` |
| arity | exactly two distinct existing `quote_ref` values, canonically ordered |
| write path | Ecology opaque admission -> Economy owner fragment -> one `GameplayCommandEnvelope` / `SettlementPlan` batch -> `GameplayEventStore.append_batch()` |
| projection/replay | existing `EconomyProjector` plus full/checkpoint-tail reconstruction |
| receipt | only the one resulting `GameplayEventStore.append_batch()` result |
| privacy | project-visible source and target quote events; existing quote fence excludes account/payment fields |
| revision | exact committed ecology event/stream/head pin plus current `gameplay:economy` head |
| idempotency | source plus canonical two-quote pair; exact duplicate replays, changed reuse rejects |

The Economy owner writes both quote events from one `OwnerAuthorizedFragment`.
Two fragments cannot write the same stream, so this package must not model the
two targets as independently appended fragments.

## Admission And Rejection

`EcologyHazardAuthority` may issue only an opaque admission bound to one
committed weather-front source and one canonical pair. `EconomyAuthorityService`
must revalidate the source event, project visibility, ecology stream revision,
source head, pair arity/distinctness, target quote existence, catalog row,
Economy head and idempotency before its one append.

Forged/missing admission, non-project source, stale ecology or Economy head,
missing target, one/three/duplicate targets, changed duplicate, and catalog
mismatch are all zero-write. No caller supplies a stream, event type, pricing
formula, owner, arbitrary target list, retry, compensation or payment command.

## Non-goals

This does not introduce arbitrary ecology fanout, a generic pricing system,
cross-domain settlement, a scheduler, a second event store, a second runtime,
or any Economy account/payment truth. It does not authorize an additional
consumer beyond this exact two-quote Economy row.
