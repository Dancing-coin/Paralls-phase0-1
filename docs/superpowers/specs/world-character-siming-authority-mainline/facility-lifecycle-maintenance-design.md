# Facility Lifecycle And Maintenance Design

Owner: `ConstructionProductionAuthority`.

`Facility` keeps the compatible main lifecycle `active | decommissioned`.
Construction phase, maintenance due/open/expired and repair state are separate
owner projections. Facility content declares capabilities, slot capacity,
condition thresholds, maintenance policy and procedural component mapping.

Every lifecycle transition pins facility revision, stream head, project/plot
binding, policy, descriptor and package provenance. Maintenance and repair use
existing owner obligations and fixed event vectors. Full and checkpoint-tail
replay must rebuild the same facility revision, lifecycle and maintenance
projection. Existing INF narrow rows are not reinterpreted by this design.

Unknown/inactive content, private or stale evidence, conflicting lifecycle,
active-run conflict, duplicate and changed-duplicate are zero-write. No
generic lifecycle or reversal semantics are implied; policy must declare
terminal/correction behavior explicitly.

New maintenance-obligation events retain the Construction facility/project
identity, current facility revision, maintenance policy reference and
pre-append stream-head pin. Replay verifies these pins before applying the
obligation to a ProductionRun. Legacy obligation events without the additive
pins remain readable without reinterpretation.

Maintenance-obligation idempotency is exact: a repeated key must match the
original run, obligation, causation and correlation fields; changed duplicates
are rejected before append.

Replay requires a non-empty `obligation_ref`; malformed obligation payloads
fail closed with the stable `construction_maintenance_obligation_conflict` code.

The event is source-controlled as
`gameplay.construction_production.maintenance_obligation_created@1` in the
existing `EventSchemaRegistry`; registration is explicit and idempotent.

The core facility/run lifecycle events (`facility_acquired`,
`facility_transformed`, `facility_decommissioned`, `run_started` and
`run_finished`) now have the same explicit source-controlled registrations.

These lifecycle schemas, maintenance, jobs, output certification and custody
schemas can be installed together through the existing aggregate registry
helper without introducing a second schema authority.

Repair and maintenance-state event variants are included in the same
source-controlled bundle, with idempotent registration and no payload rewrite.

Acquisition replay requires project privacy, the canonical facility stream and
non-empty facility/plot identity fields. It intentionally does not invent an
external Plot projection pin for legacy acquisition events.

Facility transform replay applies the same owner-bound source fence: project
privacy, canonical facility stream and matching project binding are required
before applying a kind/revision transition.

When a transform payload declares an acquisition source pin, replay resolves
the committed acquisition event and verifies its stream, privacy, facility,
project and optional revision identity before applying the transition.
Checkpoint-tail replay may satisfy this pin from the checkpoint's persisted
acquisition identity when the source event precedes the tail; full replay still
requires the committed source event itself.

Facility repair replay applies the same project/privacy/facility-stream fence;
wrong stream, private scope or conflicting project binding is rejected before
condition mutation.

Repair replay also requires condition values in `[0,1]` and a strictly
incremented facility revision; malformed or non-incrementing payloads fail
closed before projection mutation.

Applied maintenance-state replay likewise enforces project privacy, canonical
facility stream and matching project binding whenever the facility projection
is available.

State application replay also validates non-empty refs, positive stack count,
non-negative magnitude and resistance revision, returning the stable
`construction_maintenance_state_invalid` error for malformed payloads.

Facility decommission replay applies the same source fence before changing
lifecycle status; terminal active-to-decommissioned semantics remain row-bound.

The generic lifecycle family validates its acquisition source; the exact v3
mill decommission row additionally validates the committed mill-reinforcement
source event and both revision pins.
