# INF-3D Ecology Weather-Front Path Propagation Design

Status: `implemented and verified 2026-08-15; bounded Ecology-only path`

## Scope

INF-3D extends only the existing `EcologyHazardAuthority` with one bounded,
caller-driven weather-front path. A submitted path contains two to four
already-recorded ecology regions, so it can advance one to three symmetric
neighbor hops in one atomic batch. It is an ecology-internal process, not a
consumer edge, scheduler, graph truth store, or generic propagation runtime.

## Owner Contract

| Item | Contract |
| --- | --- |
| Owner | `authority:ecology` / `EcologyHazardAuthority` |
| Streams | existing `gameplay:ecology:{region_ref}` for every path member |
| Policy | closed `policy:ecology_weather_front_path@1`; `max_chain_depth=3`, `max_targets=3` |
| Events | existing `gameplay.ecology.weather_front.propagated` and `gameplay.ecology.environment.recorded` |
| Projection | existing regional ecology projection; project scope only |
| Receipt | append result from one `GameplayEventStore.append_batch()` |

The root region's committed project-visible weather is copied to each later
region in path order. Each interior region records its incoming environment
update before its outgoing frontier event on its existing stream. The path is
finite, cannot repeat a region, and every adjacent pair must be symmetric in
the canonical region records. The complete expected revision vector names
exactly the existing path streams.

```text
EcologyHazardAuthority -> GameplayCommandEnvelope
-> Ecology owner fragments (one per existing region stream)
-> one SettlementPlan / GameplayEventStore.append_batch()
-> project outbox -> regional replay -> scoped projection
```

## Admission and Rejection

- Only `authority:ecology` may submit the command, and only project scope is
  admitted.
- The path length, policy revision, tick, region uniqueness, records,
  symmetric adjacency, and complete revision vector are all checked before an
  append.
- Exact duplicates replay. A changed same-key path, stale stream revision,
  malformed/looping path, non-project privacy, missing record, or asymmetric
  adjacency is zero-write.
- This operation neither issues nor consumes an ecology consumer admission. It
  cannot write Construction, Economy, Survival, Social, Population, or branch
  truth.

## Evidence

Focused tests and a dedicated Harness profile must separately prove three-hop
success and stream shape, exact duplicate, changed duplicate zero-write,
stale-vector zero-write, path/adjacency zero-write, privacy, outbox scope, and
full/checkpoint-tail replay. No test selector may claim multiple capabilities.

## Non-goals

No fanout set, arbitrary graph traversal, autonomous propagation, hazard
mutation, retry/compensation, additional consumer edge, new authority, event
store, bus, clock, scheduler, or truth store is admitted.

Evidence: `.harness/verification/infra-ecology-weather-front-path-propagation-report.json`;
focused/dependent suites, docs and continuation gates, `git diff --check`, and
full `python -m pytest -q` (`3052 passed`) passed on 2026-08-15.
