# INF-3 Ecology And Disaster Authority Design

Status: `implemented-and-verified for the documented frost/crop vertical; broader ecology propagation remains planned`

## Purpose And Ownership

INF-3 validates immutable region/environment/resource/crop/hazard input
records and proves one frost-to-crop semantic settlement. Those record classes
are not yet persisted ecology truth, and hazard lifecycle is not event sourced.
Crop, construction, survival, economy, and population retain their own state
transitions. No new event store, scheduler, or world truth store is authorized.

`EcologyHazardAuthority.settle_frost` accepts a structured frost/crop input,
freezes the semantic/effect input, and delegates to `SemanticSettlementAuthority`
for one crop-stream append. It is not yet caller-driven due-obligation or
owner-fragment settlement; that expansion is INF-2R/INF-3R work.

## Models, Events, And Authority Chain

`EnvironmentRegion`, `EnvironmentalState`, `ResourceNode`, `CropRecord`, and
`HazardRecord` are frozen command/input records with stable identifiers and
selected revision/policy/idempotency fields. The verified `HazardRecord` does
not contain an ecology stream, record lifecycle, source refs, area, seed, or
generic templates. It may propose one frost effect; it cannot directly deduct
crop health, inventory, funds, or body resources.

The verified vertical writes `semantic.effect.settled` to the crop stream,
with hazard evidence/correlation material. The following ecology event family
is planned only: `ecology.region_registered`, `environment_updated`,
`resource_regenerated`, `crop_transitioned`, `hazard_scheduled`, `activated`,
`fragment_rejected`, `settled`, `deferred`, and `closed`. The frost vertical is:

```text
frost input -> SemanticSnapshot/effect/resistance -> SemanticSettlementAuthority
-> crop stream append_batch -> causal dossier/outbox -> scoped projection
```

## Correctness And Safety

The same hazard command and idempotency key return the original receipt. A
stale region/crop/rule revision, owner denial, unsupported effect, chain budget
exhaustion, or privacy mismatch produces a structured failure and zero writes.
Public views redact owner and evidence data; authority views retain eligible
trace references but never expose secret facts in `RuleEvaluationTrace`.

Full and checkpoint-tail replay proves the committed crop-stream semantic event
and causal projection. Ecology record projections, schema upcasting, and hazard
compensation/cancellation are INF-3R work; no persisted ecology history is
claimed by this vertical.

## Harness, Completion, And Non-Goals

`infra-ecology-disaster` has separate checks for records, frost success,
resistance attenuation, owner rejection zero-write, idempotency, revision
conflict, chain-budget truncation, public/authority privacy, causal trace,
full replay, and checkpoint-tail replay. It produces an evidence report and
updates the August status.

Complete means a formal frost vertical across ecology and crop owner plus the
listed evidence. It does not mean full climate simulation, market propagation,
civilization evolution, biological simulation, or Godot completion. A Godot
visible mirror introduced by this package must be runtime-verified before any
visible completion claim.
