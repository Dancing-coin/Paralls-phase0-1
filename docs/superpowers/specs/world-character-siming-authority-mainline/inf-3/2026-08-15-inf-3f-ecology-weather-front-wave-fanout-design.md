# INF-3F Ecology Weather-Front Wave Fanout Design

Status: `implemented and verified as a bounded Ecology-only propagation row`

## Purpose

INF-3F closes one remaining Ecology-internal propagation gap with a bounded
two-wave weather-front fanout. It extends the existing
`EcologyHazardAuthority`; it does not create a scheduler, graph runtime,
consumer edge, or non-Ecology writer.

## Closed contract

| Item | Contract |
| --- | --- |
| Owner | existing `authority:ecology` / `EcologyHazardAuthority` |
| Streams | only existing `gameplay:ecology:{region_ref}` streams named in the wave plan |
| Policy | closed `policy:ecology_weather_front_wave_fanout@1`, two waves, at most six edges |
| Events | existing `gameplay.ecology.weather_front.propagated` and `gameplay.ecology.environment.recorded` |
| Projection | existing regional environment and event-derived `frontier_edges` projection |
| Privacy | all source, target, event and outbox entries are `project` scoped |
| Receipt | the single existing `GameplayEventStore.append_batch()` result |

The caller supplies an explicit two-level edge plan, but cannot supply a
stream, event family, fragment, owner, policy, revision, or visibility. Wave
one edges must begin at the one root region. Wave two edges must begin only at
a region targeted by wave one. A region can appear as a target only once, the
root cannot be a target, and each edge must be symmetrically adjacent in the
already committed regional projection. The root's committed weather value is
copied across the whole bounded wave plan in one batch.

For every touched stream, the authority computes the exact expected revision
and rejects a caller mismatch before append. One per-stream owner fragment
contains all source-frontier and target-environment events for that stream;
the existing fragment merge then calls the one store append path. A plan is
therefore transactional: no first wave can persist without its valid second
wave, and vice versa.

## Admission and non-goals

- Exact duplicates replay; changed duplicates, stale vectors, missing records,
  private scope, malformed depth, repeated targets, non-adjacent edges and an
  over-budget plan are zero-write.
- The Construction consumer edges are unchanged by this package. This is
  Ecology-internal propagation only; no hazard, crop, economy, body, social,
  population, or Construction consequence is written by the wave-fanout path.
- It is caller-driven and bounded. It is not autonomous weather, a background
  scheduler, a generic graph traversal API, multi-round unbounded fanout,
  retry/compensation, or a generic consumer registry. INF-3G separately admits
  one exact weather-front -> Construction maintenance edge.

## Required evidence

Focused tests must separately prove the two-wave transaction, target
environment/frontier projection, exact idempotency, changed duplicate,
revision, invalid depth/adjacency, privacy, full replay and checkpoint-tail
replay. The package requires a dedicated Harness profile/report and preserved
INF-3D, INF-3E and continuation-gate predecessor evidence.

Evidence: `infra-ecology-weather-front-wave-fanout` records nine independent
selectors in
`.harness/verification/infra-ecology-weather-front-wave-fanout-report.json`.
The row remains caller-driven and uses only the existing Ecology authority.
