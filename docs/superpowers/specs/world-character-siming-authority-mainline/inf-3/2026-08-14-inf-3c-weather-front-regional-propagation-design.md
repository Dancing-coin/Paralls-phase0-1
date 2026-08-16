# INF-3C Weather-Front Regional Propagation Design

Status: `implemented and verified for one caller-driven, symmetric-neighbor, budget-one weather-front step; broader propagation remains unimplemented`

Date: `2026-08-14`

## Scope

INF-3C adds exactly one caller-driven, budget-one ecology process inside the
existing `EcologyHazardAuthority`. It propagates the source region's committed
project-visible `weather_ref` to one directly adjacent target region's existing
`EnvironmentalState`. It is not a scheduler, a generic propagation graph, or a
cross-domain consumer edge.

## Owner and write contract

| Item | Contract |
| --- | --- |
| Owner | `authority:ecology` / `EcologyHazardAuthority` |
| Streams | source `gameplay:ecology:{source_region_ref}` and target `gameplay:ecology:{target_region_ref}` |
| Command | `gameplay.ecology.weather_front.propagate` |
| Source event | `gameplay.ecology.environment.recorded` on the source stream |
| New source event | `gameplay.ecology.weather_front.propagated` |
| Target event | existing `gameplay.ecology.environment.recorded` |
| Policy | fixed `policy:ecology_weather_front_step@1`, `max_targets=1`, `max_chain_depth=1` |
| Formal path | `EcologyHazardAuthority -> GameplayCommandEnvelope -> OwnerAuthorizedFragment x2 -> build_multi_stream_atomic_event_batch_from_fragments() -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection` |

The two fragments are both authored by the same existing ecology owner. They
are disjoint by stream and are committed by one existing `append_batch()` call.
No new runtime, store, bus, clock, scheduler, authority, or projection owner is
created.

## Canonical adjacency and revision contract

`EnvironmentRegion.neighbor_region_refs` is a canonical ecology-owned,
project-visible, immutable-at-record-revision adjacency list. A propagation is
admitted only when the relation is symmetric: source lists target and target
lists source. Changing either list requires the existing revisioned
`gameplay.ecology.region.recorded` row; this package does not introduce a
separate edge stream.

The command's `expected_revisions` must contain exactly the current source and
target ecology stream heads. The source frontier event carries the source and
target region-record revisions, source and target environment revisions, policy
revision, tick, and fixed chain budget. The target environment record advances
only its existing record revision by one.

The command is caller-driven. `tick` is an ordering/evidence input only and is
not a second clock or autonomous loop.

## Privacy, idempotency, and rejection

Only project-visible input and output are admitted. `authority_only` or private
input is rejected before append. Public projection exposes source/target refs,
weather ref, tick and policy ref; authority projection additionally exposes
the exact revision vector. Outbox entries are project scoped and do not expose
causal/source internals.

Store idempotency uses the existing `(principal_ref, idempotency_key)` contract.
Unknown/asymmetric adjacency, missing regional records, stale source or target
revisions, unsupported policy, malformed tick, non-project scope, or a chain
budget other than the fixed one are zero-write rejects.

## Non-goals

- fanout or multi-hop propagation;
- hazards, retry, compensation, or obligations;
- mutation of resources/crops/hazards by this command;
- economy, survival, social, population, or construction writes;
- any consumer edge beyond the separately registered INF-3Y rows;
- automatic or background scheduling.

## Completion condition

The package is complete only after focused tests separately prove one batch
success, stale/asymmetric zero writes, duplicate idempotency, project privacy,
full/checkpoint-tail replay, a dedicated Harness profile/report, August/root
doc synchronization, `git diff --check`, and a full pytest run.

## Verification record

The focused propagation suite and dedicated Harness profile passed on
`2026-08-14`. The report is
`.harness/verification/infra-ecology-weather-front-propagation-report.json`.
This is an ecology-internal process, not a new INF-3Y consumer edge.
