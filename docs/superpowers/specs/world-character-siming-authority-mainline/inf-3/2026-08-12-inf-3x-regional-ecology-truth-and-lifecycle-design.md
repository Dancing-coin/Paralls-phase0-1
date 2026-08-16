# INF-3X Regional Ecology Truth And Lifecycle Design

Status: `implemented and verified for canonical regional record and retirement rows; broader ecology lifecycle remains planned`

Continuation is guarded by `infra-continuation-gate`, which independently
asserts this owner/event map and the empty INF-3Y enabled-edge set before a
future package proceeds. The gate is declarative and creates no new writer.

## Purpose and inherited baseline

INF-3X specifies the missing ecology truth slice behind the verified frost/crop
vertical: durable region/environment/resource/crop/habitat state and lifecycle.
The existing `EcologyHazardAuthority.settle_frost`, semantic bridge, event
store, causal projection and frost report are reusable. They do not establish
an ecology stream owner, regional projection source, resource regeneration or
crop lifecycle.

## Owner admission and hard stop

`EcologyHazardAuthority` in `backend/app/gameplay/ecology_runtime.py` is the
sole admitted extension owner for regional environment/resource/hazard facts:
it already declares ownership of hazard facts, accepts the existing
`GameplayEventStore`, and defines `EnvironmentRegion`, `EnvironmentalState`,
`ResourceNode`, `CropRecord`, and `HazardRecord`. INF-3X extends that authority
and its existing store spine; it does not introduce `EcologyRecordAuthority` as
a second service. Crop-effect settlement still remains the named semantic/
domain path, so implementation must prove no competing crop stream ownership.

Before lifecycle code begins, the plan must add canonical ecology stream names,
event constructors, revisioned scoped projections and an
`OwnerAuthorizedFragment` builder to this authority. It must not own prices,
balances, body resources, inventory, social facts, population or civilization.
If that extension would require a second store, coordinator-owned events, or a
projection write, stop the package rather than repurposing another component.

### 2026-08-13 canonical contract admission

Fresh predecessor reports at
`.harness/verification/infra-obligation-lifecycle-report.json`,
`.harness/verification/infra-ecology-disaster-report.json`, and
`.harness/verification/infra-regional-ecology-report.json` prove the existing
spine and the narrow frost source. They do not supply ecology truth, so INF-3X
extends the already admitted `EcologyHazardAuthority` over the one existing
`GameplayEventStore`; no new store, runtime, scheduler, or owner is introduced.

The sole ecology stream pattern is `gameplay:ecology:{region_ref}`. The owner
is `authority:ecology`; it is the only principal permitted to create the
following owner fragments and append their resulting batch:

| Record | Create/update event | Retire event | Source revision | Visibility |
| --- | --- | --- | --- | --- |
| region | `gameplay.ecology.region.recorded` | `gameplay.ecology.region.retired` | ecology region stream | project / authority_only |
| environment | `gameplay.ecology.environment.recorded` | `gameplay.ecology.environment.retired` | ecology region stream | project / authority_only |
| resource | `gameplay.ecology.resource.recorded` | `gameplay.ecology.resource.retired` | ecology region stream | project / authority_only |
| crop | `gameplay.ecology.crop.recorded` | `gameplay.ecology.crop.retired` | ecology region stream | project / authority_only |
| hazard | `gameplay.ecology.hazard.recorded` | `gameplay.ecology.hazard.retired` | ecology region stream | project / authority_only |

Each payload carries the frozen record, `record_ref`, causation/correlation
references, source revision, and the owner-selected visibility policy. The
authority projection is reconstructed exclusively from these events; public
scope exposes project-visible record summaries without evidence, and authority
scope retains causal/evidence references. The fragment map is the ten explicit
event rows above. `settle_frost` continues to use its existing semantic crop
path and does not become an ecology record writer.

When available, writes are authority -> envelope/SettlementPlan ->
`GameplayEventStore.append_batch()` -> outbox/replay -> ecology and dependent
scoped projections. Inputs from Godot, sensors, creator/MCP, LLM and Siming
are evidence/proposals only.

## Required contracts

Versioned records are `EnvironmentRegion(region_ref, climate_profile,
biome_tags, carrying_capacity, jurisdiction_ref, revision)`,
`EnvironmentalState(region_ref, temperature, moisture, contamination, weather,
effective_tick, revision)`, `ResourceNode(node_ref, substance_ref, quantity,
regeneration_policy, extraction_state, revision)`, `CropOrPopulation(entity_ref,
growth_state, health, habitat_refs, revision)`, and `HazardEvent(hazard_ref,
area, duration, severity, effect templates, causal parents, revision)`.
Every record has stable identity, owner/source revision, visibility and digest.

The ecology event family must explicitly include create/update/retire region,
environment sampled/changed, resource extracted/regenerated, crop planted/
grown/damaged/harvested/retired, habitat changed and hazard observed/resolved.
Lifecycle ticks are `ScheduledObligation`s using INF-2X only after an ecology
owner fragment exists. Event payloads use causality/correlation fields but do
not directly contain economy, survival or population consequences.

## Safety, privacy, replay and completion

Commands pin region, active semantic/rule, policy and owner revisions plus
idempotency key. Unknown region/node/crop, illegal transition, stale revision,
negative quantity, outside jurisdiction, invalid evidence, privacy denial or
altered duplicate key reject before append with zero writes. Public views may
show declared aggregate state; actor views show observed facts; owner/authority
views retain source evidence. Filters cannot change settlement input.

Full and checkpoint-tail replay must rebuild identical regional/resource/crop/
hazard hashes and causal references. Event reader migrations/upcasters and
retirement/forward correction policy must be defined before a schema change;
history is never deleted. Rollback means retiring future configuration or
appending owner-specific correction/compensation only when its event map
exists; it never rewrites ecology history.

## Harness and completion

`infra-regional-ecology-truth` independently proves every canonical recorded
and retired row, one existing ecology stream/append/outbox path, region and
record revision zero-write, unknown retirement zero-write, privacy/bundle
overwrite zero-write, idempotency, scoped projection, single-record update and
full/checkpoint-tail replay. Evidence:
`.harness/verification/infra-regional-ecology-truth-report.json`.
Non-goals remain scheduler, regeneration/growth, retry, compensation, weather
algorithms, market/body/social propagation, new runtime/store, Godot proof and
P6/P7.
Completion is limited to the record/event rows independently proven by that
profile; the owner admission does not itself constitute lifecycle evidence.
