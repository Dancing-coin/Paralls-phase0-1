# Embodied Action Controller And Local Observation Design

Status: `implemented-foundation; broader-atom-and-runtime-coverage-planned`

Date: `2026-07-29`

Revision: `2026-07-31` (review remediation)

## Purpose

Define `EmbodiedActionController` as the Godot-local realization owner for an
already authorized semantic action. It consumes stable registry IDs and an
`EmbodiedActionRequest`, executes at frame rate, and reports bounded terminal
observations without owning semantic settlement.

The bounded controller route is now implemented and Godot-runtime-verified for
the current slices: typed phase transitions, terminal observations, safe
recovery, the legacy/controller route gate, and reviewed action-asset phase
binding. This does not claim a production clip graph, full CharacterMotor/IK
integration coverage, or broad scene-family closure.

## State Machine

```text
idle
  -> acquire_target
  -> reserve_stance
  -> plan_approach
  -> navigate
  -> align
  -> prepare
  -> execute_contact
  -> observe
  -> recover
  -> terminal

any active state -> abort -> recover -> terminal
any active state -> interrupted -> recover -> terminal
```

Each state has a timeout, cancellation policy, trace event, and one of the
typed terminal statuses defined by the master design. Local recovery restores
movement/animation ownership before accepting the next request.

## Local Responsibilities

- resolve registry IDs into nodes, anchors, colliders, and safe local profiles;
- use NavigationServer/NavigationAgent or an equivalent bounded local path
  implementation for approach and stance;
- reserve a stance slot locally and reject collision/occupancy conflicts;
- align heading, distance, reach, and animation contact window;
- run an action atom through existing/local animation, IK, and motion-warp
  integration points;
- collect contact, body, target, and environment observations at the contact
  window and after a bounded settle interval;
- cancel safely on target invalidation, collision interruption, authority
  expiration, controller replacement, scene unload, or timeout.

## Prohibited Responsibilities

- LLM/VLA-requested per-frame bones, transforms, velocities, or impulses.
- Direct calls that declare an ESM/world result successful.
- Sending full bone streams to backend; existing debug-only replay retention
  remains the maximum low-level skeletal evidence path.
- Holding a multi-actor agreement itself; it only consumes an assigned session
  slot and cancellation directive.

## Local Observation Contract

`LocalPhysicalObservation` is evidence, not a command. It includes observed
contact pairs, selected collider/anchor refs, relative pose summary, bounded
impulse/velocity/final-pose summary when applicable, scene/binding revision,
timestamp, and artifact refs. It intentionally excludes arbitrary physics
engine state dumps and raw frame streams.

The `kick-chair` observation rule requires a matching actor foot/contact
collider and target collider during the contact window, then an object
state/final-pose observation. An animation-finished signal alone is invalid.

## Migration Boundary

The backend selects exactly one `realization_route` in preflight:
`legacy_character_replica` (default) or `embodied_controller_v1` (only a
reviewed actor/scene/action feature-gate allowlist). The selected route is
immutable for that attempt and is carried in its execution grant.

For `embodied_controller_v1`, `CharacterReplica` is only the host/animation
integration point. It must not repeat range/LOS/approach checks, call the
legacy interaction submit path, or emit legacy status as an authority input.
`EmbodiedActionController` alone owns local navigation, contact observation,
and its typed transport. For `legacy_character_replica`, controller messages
are ignored and no controller is created. `CharacterMotor` remains locomotion
machinery under the selected local owner; neither host gains intent selection.

The feature gate may be disabled only for new attempts. Active embodied
attempts first receive an authority cancellation/recovery directive and settle
their terminal non-commit record; the route is never switched mid-attempt.

## Acceptance Criteria

1. The controller runs at local frame rate and transitions through every first
   closure state with a traceable attempt ID.
2. It completes approach/alignment before enabling the contact window; it does
   not issue a kick merely because an actor has a target ID.
3. Navigation block, target movement, stance reservation conflict, lost
   collider, timeout, cancellation, and interruption return distinct terminal
   observations and recover local control.
4. Contact observation distinguishes actual contact, missed contact, and a
   fixed/blocked target without claiming authoritative outcome.
5. Runtime verification proves a real scene node, path, collider, and action
   controller script execute without immediate Godot errors.
6. A mixed fixture proves the feature gate starts only one local route and that
   legacy `character_actor_status` cannot settle or advance an embodied action.

## Dependencies

- Scene affordance registry.
- Existing CharacterReplica/CharacterMotor/CharacterRuntimeState only as
  integration hosts, not as semantic authority.
- Existing embodied skeletal provider/replay policy for safe debug evidence.
