# INF-3R Regional Ecology Propagation Expansion Design

Status: `implemented and verified for one fixed frost-to-due-production-finish edge; broader ecology propagation remains planned`

Date: `2026-08-12`

## Purpose and owners

INF-3R expands the frost/crop baseline by one named edge only:
`EcologyHazardAuthority.settle_frost` in
`backend/app/gameplay/ecology_runtime.py` to
`ConstructionProductionAuthority.build_due_finish_fragment` in
`backend/app/gameplay/construction_production_runtime.py`. The target stream is
`gameplay:construction_production:{facility_ref}`. Drought, flood, fire,
contamination, survival, economy, and population propagation are not authorized
until separately mapped to existing owner fragments.

## Admission results: 2026-08-13

The first admission gap is closed by verified `INF-3R-A`: a committed crop
frost event now carries owner-supplied plot/provenance, and the existing
construction projection deterministically selects one due started run with its
production stream revision. This establishes neither a consequence write nor a
recipe owner.

Second admission is closed by verified `INF-3R-B`: the existing construction
owner carries an immutable `recipe_ref`/`output_item`/`duration_ticks` snapshot
on its committed `run_started` event and rebuilds an authority-only source
revisioned reader from the same production stream. Ecology, a coordinator,
Godot, Siming, or caller data still may not manufacture a `Recipe`. R-B is
input admission only; no consequence test has yet passed and no production
finish event has been written from frost.

The path remains:

```text
frost observation -> EcologyHazardAuthority semantic evaluation
-> ConstructionProductionAuthority due-finish fragment -> append_batch
-> outbox/replay -> redacted region and causal projections
```

No ecology module may set prices, inventory, body resources, relationships, or
population state directly. Godot and Siming can supply evidence/proposals only.

## Records and events

The first consequence payload extension is
`ProductionFrostPropagationRef`: frost hazard reference, committed crop source
event/revision, production run/facility refs, committed recipe source/revision,
finish tick, semantic/rule/policy revisions, causal parent, idempotency key,
and visibility. It is carried by the existing production event, not a regional
store.
`RegionClimatePolicy`, resource regeneration, habitat aggregates, and other
hazard families are blocked pending a concrete owner and projection map.

Crop and production consequence events retain common hazard/trace/correlation
refs. The sole edge has a fixed frost predicate, fan-out one, and no delayed
obligation or compensation. A generic `PropagationEdge` model is deferred.

## Exact admitted settlement contract

`EcologyHazardAuthority` may convert only its committed `FrostPropagationSource`
into `ConstructionFrostFinishCommand`. This is a proposal: its fields are the
source event id, crop stream revision, hazard/crop/plot/region refs, due tick,
semantic/rule/policy revisions, causal parents, and visibility. It contains no
run, facility, recipe, target stream revision, or production event payload.

`ConstructionProductionAuthority.settle_frost_due_finish` is the sole writer.
It re-reads and matches the committed crop semantic event, rejects a stale or
private-mismatched source, uses its own `select_due_run_for_plot`, retrieves
the matching `recipe_for_run`, builds only `build_due_finish_fragment`, and
uses the existing `build_multi_stream_atomic_event_batch_from_fragments` plus
`GameplayEventStore.append_batch()` once. The sole new data is provenance on
the existing `gameplay.construction_production.run_finished` event. The
construction owner derives idempotency from the committed source event;
the source cannot fan out or make a second production write.

The consequence event carries `frost_propagation` only in its project/authority
payload: source event/revision, hazard/crop/plot/region refs, due tick,
semantic/rule/policy revisions and causal parents. Public scoped projection
exposes run/facility/finished tick only; evidence and causal provenance remain
authority scoped. `retry_policy` and `compensation_policy` are not admitted
for ecology and reject before append.

## Determinism, zero-write, privacy

Propagation uses fixed phase order, integer/fixed-precision values, and a
causal chain budget. The sole edge can produce at most one production fragment;
it cannot schedule follow-up work until INF-2R has a committed lifecycle event
for that owner.
Unknown region, stale environmental/target revision, forbidden edge, exceeded
budget, unsupported hazard, owner denial, privacy mismatch, or idempotency key
reuse with changed input rejects before append and commits nothing.

Region public views expose only declared public state; actor views add observed
facts; owner and authority views retain necessary source evidence. Hazard trace
redaction is deterministic and cannot alter environmental truth or settlement.

## Replay, recovery, completion

Full and checkpoint-tail replay must reconstruct the named frost-to-production
edge, causal ancestry, and scoped projections. Schemas use versioned readers/
upcasters. Recovery is rejection before append; compensation is blocked until a
production compensation event exists. Historical facts remain append-only.

Planned profile `infra-regional-ecology` separately proves the named frost to
production edge, stale source/target rejection, duplicate, compensation/retry
zero-write rejection, privacy, full replay, checkpoint-tail replay, and reader
migration. Resistance/attenuation and chain truncation remain the committed
frost-source semantics already proved by `infra-ecology-disaster`, not a
second production evaluator. Non-goals: regional record persistence,
drought/flood/fire/contamination, delayed propagation, compensation, automatic
market/social effects, a new regional truth store, and Godot runtime completion.

## Verification record

On 2026-08-13, `infra-regional-ecology` independently passed 13 named
capability assertions. Its focused construction/ecology suite passed 38 tests,
the repository suite passed `2569 passed`, and `git diff --check` passed.
Evidence is at `.harness/verification/infra-regional-ecology-report.json`.
This completes INF-3R only for the fixed committed frost source to one due
construction production finish fragment; it does not complete INF-3X, INF-3Y,
generic hazard propagation, retry, compensation, or a regional truth store.
