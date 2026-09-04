# 3D Scripted-Mystery Action Platform Design

Status: `design-revised; implementation-authorized`

## Purpose

Provide the first reusable action platform for a 3D scripted-mystery and
asymmetric pursuit game. The first content package is a small indoor case with
investigation, stealth, pursuit, light non-lethal conflict and a two-level death
model. The platform is intentionally smaller than a full real-time combat or
sports engine, but its contracts remain usable by those future families.

## Reuse-first architecture

The platform extends existing code instead of creating parallel truth systems:

- `ActionPrimitiveDefinition`, `ActionIntent`, `PhysicalFact`, `LogicalFact`
  remain the semantic and evidence primitives.
- `EmbodiedActionController` remains the local action playback, navigation,
  alignment, cancellation and recovery host.
- `CharacterEmbodimentAssetRegistry` remains the action-asset source.
- `SkillPathGameplayGate` and `ResourceBodyActionSettlementService` remain the
  skill, resource and body read/settlement gates.
- `InvestigationConflictAuthority` is extended behind a compatible conflict
  façade; it is not replaced by a second conflict runtime or store.
- Every durable result continues through
  `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.

The action layer never owns inventory, skill, body, quest, social, economy or
world facts. It produces validated evidence and delegates each consequence to
the existing owner.

## Action graph content

`ActionGraphDefinition` is a package-local finite-state composition of existing
`ActionPrimitiveDefinition` nodes. It is not an executable script and does not
replace the primitive registry.

Each graph declares:

```text
graph_ref / graph_revision
action_family
role_refs
primitive_refs (author-ordered)
nodes (author-ordered)
edges (author-ordered)
capability_refs
observation_requirements
asset_refs
interruption_policy
recovery_policy
policy_revision
```

Each node references one registered primitive and adds only orchestration data:

```text
node_ref
primitive_ref
phase
duration_window
cancel_targets
condition_refs
asset_ref
contact_marker_refs
```

Each edge contains `from_node`, `to_node`, `trigger`, `priority` and registered
`condition_refs`. Conditions are limited to registered capability/state,
distance/visibility/sound bands, cooldown and policy predicates. No arbitrary
Python, GDScript, expression evaluator, network, file or clock access is
allowed in package content.

Admission rejects duplicate or unknown references, unreachable nodes, cycles
without an explicit bounded loop, missing recovery/terminal paths, conflicting
edges, unregistered primitives/assets/policies and non-canonical arrays.

## Fixed action window

The first runtime uses a fixed one-second logical window. Godot may render
continuous movement and animation, but the authority accepts one ordered
`ActionWindowIntent` per actor/window:

```text
attempt_ref
encounter_ref
actor_ref
window_index
window_start_tick / window_end_tick
graph_ref / graph_revision
node_ref
target_refs
expected_revision_vector
local_position_sample
facing_sample
visibility_sample
sound_sample
contact_sample
navigation_revision
collision_revision
occlusion_revision
sound_zone_revision
deterministic_seed
evidence_refs
```

The server/host protocol is designed now even though the first implementation
may run locally. Duplicate windows replay the original result; changed payload,
out-of-order windows, stale revisions and missing evidence are zero-write.

## Frozen spatial evidence

The authority does not run a second continuous physics engine. It re-evaluates
the submitted samples against a frozen, versioned spatial snapshot:

```text
navigation_revision
collision_revision
occlusion_geometry_revision
sound_zone_revision
```

The snapshot supplies walkability, distance, line-of-sight occlusion, sound
bands, hide-spot occupancy and contact bounds. A client cannot directly assert
discovered, hit, captured or dead. A mismatch between submitted measurements
and the frozen snapshot rejects the whole window.

## Conflict and consequence ownership

The existing P5 conflict authority becomes the compatible implementation host
for the following bounded outcomes:

```text
encounter_started@1
action_window_resolved@1
control_changed@1
terminal_outcome_recorded@1
encounter_closed@1
```

The window result carries typed sub-results for movement, visibility, sound,
pursuit, contact and terminal state. This keeps the initial event surface
small and leaves room for later sports/combat revisions to split event types.

Conflict writes only conflict facts. Consequences are delegated independently:

- Body: injury, imbalance, recovery;
- Inventory: item/tool condition or consumption;
- Quest/Knowledge: clues, exposure and case progress;
- Social: witness, reputation and relationship facts;
- Economy/Contract: reward, compensation or obligation;
- Character/World: persistent death only after an explicit confirmation.

The first role package is `survivor`, `pursuer` and `witness`. Role profiles
declare permitted graph refs, perception profile, control effects, capture
policy and death policy. No role is hard-coded into the core schema.

## Death boundary

The initial lethal path is two-level:

```text
case_death_recorded
-> world_death_commit_proposed
-> explicit player/story confirmation
-> world_death_committed
```

Case death is terminal for the current encounter. It does not automatically
rewrite the persistent Character record. The first implementation verifies
accept/reject confirmation, replay, privacy and zero-write; inheritance,
replacement characters and broad social/economic aftermath remain separate
future owner contracts.

## Godot and voice presentation

Godot keeps the existing third-person embodiment path and adds a first-person
camera option that changes presentation only. The local controller handles
playback and speculative state; committed action results drive the UI and TTS.

The common transition surface is:

```text
approaching -> preparing -> loading -> ready -> active
-> suspending -> returned | rejected
```

UI and voice templates are package content with revision/provenance; they never
decide a world fact. Rejection clears speculative action, camera and panel state
and returns to the latest committed checkpoint.

## Creator and Siming boundary

Creator Skill and Siming Director are deliberately separate from this runtime
MVP. They will consume the stable contracts above:

```text
Creator GameBrief -> ActionGraph/package draft -> preview/replay -> admission
Siming signal -> choose admitted graph/package variant -> owner validation
```

Neither may inject graph nodes, select owner/event/stream/privacy, or directly
write conflict, body, inventory, account, relationship or death facts.

## Acceptance package

The reference package is one small hospital/warehouse case with three rooms,
two hide spots, two occluders, two sound zones, one door, one clue, one player,
one Character-agent pursuer and one witness. It proves movement, stealth,
search, pursuit, intercept, light conflict, capture, escape, case death,
explicit world-death confirmation, privacy, idempotency, zero-write and replay.

This design does not claim a complete *Dead by Daylight* or *NBA 2K* system.
It establishes the reusable action/observation/conflict seam those future
packages can extend without a second runtime.
