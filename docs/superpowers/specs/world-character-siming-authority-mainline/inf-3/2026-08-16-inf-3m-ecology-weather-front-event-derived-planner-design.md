# INF-3M Ecology Weather-Front Event-Derived Planner

Status: `implemented and verified as a bounded Ecology-only event-derived planner`

## Scope

INF-3M closes one specific gap left by INF-3D/3E/3F: weather-front expansion
is currently caller-shaped because callers provide the path, targets, or waves.
This package derives a bounded next-wave proposal from one already committed,
project-visible `gameplay.ecology.weather_front.propagated` event and the
canonical `neighbor_region_refs` in the existing Ecology projection.

The package remains Ecology-only. It adds no consumer edge, registration API,
background scheduler, clock, event store, or alternate projection owner.

## Closed owner contract

| Field | Contract |
| --- | --- |
| Owner | existing `authority:ecology` / `EcologyHazardAuthority` |
| Streams | existing `gameplay:ecology:{region_ref}` only |
| Source | committed project-visible `gameplay.ecology.weather_front.propagated` |
| Events | existing `weather_front.propagated` and `environment.recorded` |
| Policy | closed `policy:ecology_weather_front_event_planner@1`; max two waves, three first-wave targets, six total edges |
| Projection | existing `regional_projection(scope="authority")` and `regional_replay()` |
| Privacy | source and all planned writes are `project`; non-project source is rejected |
| Revision | caller pins every touched Ecology stream in `GameplayCommandEnvelope.expected_revisions`; owner rechecks before append |
| Idempotency | existing principal + command idempotency key and wave-plan digest; changed duplicate is zero-write |
| Receipt | only the result of the one existing `GameplayEventStore.append_batch()` |

## Proposal semantics

`propose_weather_front_wave_plan_from_event(source_weather_event_id, policy)`
reads, but does not write. The source event's `target_region_ref` becomes the
frontier root and its `source_region_ref` is excluded to prevent immediate
backtracking. Candidates are derived from committed region records, require
symmetric adjacency, exclude visited regions and environments already carrying
the source weather, and are sorted lexicographically before the fixed budget is
applied. The plan may contain one or two non-empty waves; no caller-supplied
edge/path is accepted by the planner.

The plan records the source event id/revision, root, prior source, weather, tick,
waves, policy revision, and a deterministic digest. The commit method re-reads
the source event and projection, verifies the digest and source visibility, then
delegates the validated waves to the existing Ecology owner batch builder.

## Rejections and non-goals

Missing, private, malformed, stale, or non-Ecology-stream source events; no eligible
frontier; forged plan digest; invalid envelope scope; changed duplicate; and
revision conflict all reject before `append_batch()` and prove zero write.

This is not autonomous scheduling, unbounded graph traversal, a generic graph
runtime, a generic consumer registry, a cross-domain settlement, or branch
promotion. Existing fixed Construction/Organization/Economy edges are
unchanged.

## Evidence gate

Focused tests must independently prove deterministic proposal, source stream/privacy
admission, no-target zero-write, successful owner append, duplicate and changed
duplicate, revision conflict, project outbox redaction, and full/checkpoint-tail
replay. A dedicated Harness profile/report and the INF-3 predecessor reports are
required before this package is called implemented-and-verified. The dedicated
report explicitly requires current green `infra-regional-ecology-truth` and
`infra-ecology-weather-front-wave-fanout` predecessor reports with an evidence
revision equal to the current workspace revision.
