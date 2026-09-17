# Character Physics, Motion, And Contact Sub-Specification

Date: `2026-09-14`

Status: `final child specification of the unified character action foundation`

Parent:
`2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`

## Purpose And Boundary

This specification defines how concurrent action and locomotion contributions
become a Godot physics command, how collision/contact evidence is produced,
and where physical feasibility stops before ESM/Gameplay semantic settlement.

It does not make Godot a world-truth authority, does not define damage or
inventory effects, and does not select a multiplayer physics server. It uses a
kinematic `CharacterBody3D` actor path for the first milestone.

## Ownership

| Concern | Owner | Output |
| --- | --- | --- |
| Control and action proposals | Player, CharacterAgent, program, INF adapter | leases and requests |
| Action/resource arbitration | `ActorActionArbiter` | admitted instances and claims |
| Contribution composition | `MotionContributionComposer` | one `PhysicsMotionCommand` |
| Collision execution | `CharacterMotor` + `CharacterBody3D` | actual motion and collision state |
| Physical evidence | Motor/contact sensors | provisional `PhysicsContactEvidence` |
| Semantic consequence | ESM/Gameplay authority | committed event/result |
| Visual pose | `RolePresentationAdapter` | animation and local modifiers |

No presentation node, action asset, ESM proposal, or network consumer may call
`move_and_slide()`, write `velocity`, or write the actor world transform.

## Fixed-Tick Data Flow

```text
ControlLeaseSet + ActionInstanceSet
        -> ActorActionArbiter
        -> MotionContribution[]
        -> MotionContributionComposer
        -> PhysicsMotionCommand(T)
        -> CharacterMotor
        -> PhysicsContactEvidence(T)
        -> same-tick marker/evidence join -> ActionAttempt / local runtime projection
```

Rendering may sample the latest immutable state but never advances the actor
simulation. Every command and evidence record includes `physics_tick`.

## Contracts

### MotionContribution

```text
MotionContribution {
  actor_ref
  physics_tick
  source_kind             # locomotion | action | impulse | runtime_correction
  source_id
  action_instance_id?
  desired_velocity?
  root_delta?
  impulse?
  facing_delta?
  constraint_refs[]
  priority
  contribution_revision
}
```

`root_delta` is a candidate extracted from a qualified animation. It is never
a permission to translate the world body directly.

### PhysicsMotionCommand

```text
PhysicsMotionCommand {
  actor_ref
  physics_tick
  desired_velocity
  root_delta
  impulse
  runtime_correction
  facing
  vertical_mode
  collision_policy
  support_requirements[]
  physics_profile_ref
  source_digest
}
```

The composer applies the canonical operation order:

1. choose the admitted continuous-control velocity;
2. apply permitted action/root contribution;
3. add impulses in stable `action_instance_id` order;
4. apply a `runtime_correction` only within its declared envelope;
5. clamp speed, acceleration, vertical launch, root delta, and correction;
6. pass the result to Motor for gravity, sweep/collision, slide, and grounding.

An action cannot create a second final writer for `root_translation` or
`physics_body`. A correction does not bypass collision handling.

### PhysicsContactEvidence

```text
PhysicsContactEvidence {
  evidence_id
  actor_ref
  physics_tick
  body_revision
  action_instance_id?
  contact_marker_id?
  grounded
  support_ref?
  collider_refs[]
  hit_sensor_refs[]
  contact_points[]
  motion_command_digest
  local_only: true
}
```

`PhysicsContactEvidence` is bounded and provisional: at most `32` collider
references, `16` hit-sensor references, and `32` contact points, with a
serialized size no greater than `16 KiB`. Exceeding a bound emits
`payload_limit_exceeded` and drops the evidence record; no truncation is
allowed. Evidence is joined to an `ActionAttempt` only at the same
`physics_tick` settlement boundary.

This is provisional evidence. It can support diagnostics and an
`ActionAttempt`, but it cannot settle a world consequence.

## Phase 1 Weapon Evidence

The `weapon_hit_volume:<id>` claim identifies a qualified local sensor or
attachment envelope; it is not a damage authority. A melee action may attach
the sensor references and contact points to `PhysicsContactEvidence`. A
hitscan action may attach a bounded local ray/origin observation as advisory
evidence. Both forms remain `local_only=true`, are tied to the action instance
and physics tick, and must be revalidated by ESM/Gameplay before any target,
damage, resource, or object-state change.

Holding a weapon uses the declared `EquipmentBinding` attachment mode. A
visual/kinematic attachment is the Phase 1 default. A dynamic `RigidBody3D`
joint is not a general held-item solution and is outside the first milestone.

## Physical Resource Claims

In addition to visual chains, actions may claim:

```text
physics_body
support_contact
interaction_reach
weapon_hit_volume:<id>
target_occupancy:<id>
ragdoll_body
```

Two upper-body actions can be visually disjoint but physically conflicting.
For example, a sword swing and an interaction action may both claim the same
right-hand reach or target occupancy. The scheduler rejects, queues, or
preempts them using the same deterministic claim rules as visual resources.

## Root Motion And Locomotion

The action descriptor declares one of:

- `hold`: no root motion while awaiting authority;
- `bounded_continue`: continue only inside a registered safety envelope;
- `reversible_continue`: allow a small reversible contribution and recover on
  rejection or timeout.

Locomotion remains a control lease even when a leg action uses
`drive_locomotion` or `replace_locomotion`. The lease is paused or limited and
resumes by revision after the action recovers; it is not silently discarded.

## Failure Semantics

| Condition | Local result | Authority implication |
| --- | --- | --- |
| wall/slope/step blocks command | Motor slides, clamps, or cancels by profile | send evidence only if an attempt needs it |
| support lost | status/physics constraint changes next tick | ESM may reject an unsupported interaction |
| root envelope exceeded | clamp and emit diagnostic | asset/profile qualification failure if repeated |
| stale `runtime_correction` | ignore by projection revision | request runtime resync in connected mode |
| local contact without valid marker | evidence only | no semantic attempt |
| marker without physical support | attempt carries failed/uncertain evidence | ESM/Gameplay revalidates and may reject |

Mode B `runtime_correction` is a Gameplay/runtime projection contribution and
is still collision-validated by Motor. Mode C `body_correction` is future-only,
requires `PhysicalAuthority`, `authority_epoch`, `body_revision`, and
`physics_tick`, and travels on a separate body stream. Neither correction type
is a permission to write a Transform outside Motor.

## Replay And Verification

The replay contract compares normalized `PhysicsMotionCommand`, evidence digest,
authority result, and final projection. It does not promise bitwise replay of
arbitrary Godot dynamic rigid-body scenes. Phase 1 verification must cover
walls, slopes, steps, support loss, root-motion clamping, simultaneous impulse
ordering, and no direct Transform writes outside Motor.

## Deferred Work

- dynamic rigid-body world simulation;
- ragdoll as a physical authority;
- server-authoritative physics worker;
- cross-machine bitwise Godot physics determinism;
- automatic runtime inference of physical claims from animation curves.
