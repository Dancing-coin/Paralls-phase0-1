# Scene Affordance Registry Design

Status: `awaiting-user-review`

Date: `2026-07-29`

Revision: `2026-07-31` (review remediation)

## Purpose

Define `SceneAffordanceRegistry` as the authoritative-compatible scene binding
and query layer used by embodied realization. It makes known Godot entities
addressable as constrained, revisioned action targets without converting the
engine scene itself into backend world authority.

## Ownership

- Godot owns live node/collider/nav binding and high-frequency measurement.
- Backend owns the reviewed semantic registry record, policy revision,
  authorization, and resulting world state.
- The registry synchronizes bindings and observations; it does not settle an
  action or infer arbitrary affordances from a node name.

## Registry Record

```text
SceneAffordanceRecord
  entity_ref, scene_id, scene_instance_id, binding_revision
  semantic_type, semantic_tags, authoritative_state_ref
  local_binding: node_ref, collider_refs, navigation_footprint_ref
  anchors[]: anchor_id, role, local_transform, reach_constraints
  affordances[]: affordance_id, action_semantic, preconditions,
                 execution_profile_ref, observation_rule_ref, policy_ref
  physical_profile_ref?, visibility_policy, evidence_refs
```

`node_ref` is local implementation metadata and must never become a callable
remote node path. Backend requests use only stable entity/anchor/affordance
IDs. Godot resolves those IDs inside the active scene instance.

## Required Rules

- Every record is scoped to `scene_id + scene_instance_id`; an ID cannot bind
  across loaded scene instances accidentally.
- A binding revision changes when node, collider, anchor, physical profile, or
  enabled affordance changes. In-flight attempts pin it.
- Anchor roles are typed: `approach_stance`, `contact`, `grip`, `place`,
  `handoff_source`, `handoff_target`, `social_slot`, and `observation`.
- Affordance availability is not a settlement result. It can be `available`,
  `blocked`, `unknown`, or `stale`, with explanation refs.
- Registry state supports known authored assets. VLA may attach an advisory
  candidate to a record only after a deterministic binding review; VLA cannot
  create an active physical affordance directly.
- Records expose no actor-private mind/relationship fields. Actor-specific
  permission and capability checks happen in authority preflight.

## Existing Grounding Inputs And Identity Rule

The registry is a reviewed realization/policy layer over existing grounding; it
must not create a parallel scene-identity system. Its record consumes, retains,
and validates these read-only inputs:

- `SceneSpaceModelExtractor` space, node, anchor, collider, and navigation
  refs for the loaded scene;
- `RuntimeOccupancySampler` occupancy/freshness refs for stance and target
  availability;
- the `PerceptionInputFrame`/`PerceptionQueryFrame` grounding catalog for
  known entity, collider, anchor, and bounded affordance refs.

`entity_ref`, collider refs, and anchor refs in a record are exactly the
reviewed catalog identities for that scene instance. The registry may attach an
execution profile, observation rule, authority policy, and local binding-health
state; it must reject any identifier disagreement rather than translate through
a private alias. The catalog makes a reference resolvable, not authoritative or
visually proven. A VLA candidate is accepted only when it names a catalog member
and passes deterministic registry review; it cannot mint an ID or activate an
affordance.

## First Chair Record

`chair_01` registers `kick` with: a stance anchor, foot-contact anchor,
collider ref, `RigidBody3D` physical profile, upright/tipped observation rule,
force policy, and a binding revision. A fixed-chair variation uses the same
semantic affordance but returns a policy/physical constraint before or after
the observed attempt as appropriate.

## Failure Semantics

| Condition | Required result |
| --- | --- |
| unknown entity/affordance/anchor | `registry_target_unknown`; no controller start |
| stale scene or binding revision | `registry_binding_stale`; refresh then re-preflight |
| local node/collider missing | `registry_binding_unhealthy`; disable record and emit evidence |
| anchor unreachable/occupied | bounded blocked result; no implicit alternate target |
| VLA conflict | retain registry truth, record advisory conflict, continue or request review |

## Acceptance Criteria

1. The scene can register/query `chair_01` with stable IDs and no raw node path
   crossing the backend contract.
2. Unload/reload, changed collider, missing anchor, and stale occupancy input
   each invalidate or block an old binding deterministically.
3. A request pins a specific record revision and cannot execute against a
   later modified binding without a new preflight.
4. Godot resolves the same binding to a real node, collider, stance anchor,
   and contact anchor at runtime.
5. Registry data is usable by controller and authority but does not expose a
   direct world-state write operation.

## Dependencies

- Master design in this tree.
- Existing `SceneRuntimeAdapter`, `InteractiveObject`, actor/entity IDs,
  `SceneSpaceModelExtractor`, `RuntimeOccupancySampler`, PQF grounding catalog,
  L1 spatial facts, and future gameplay ability-affordance projection.
