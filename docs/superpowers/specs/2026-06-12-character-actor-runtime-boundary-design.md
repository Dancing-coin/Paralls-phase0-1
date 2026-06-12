# Character Actor Runtime Boundary Design

## Problem

The current Phase 0 demo already has enough working pieces to support a unified actor substrate:

- `CharacterA` and `CharacterB` already use `CharacterReplica` plus `KnightRoleSkin`
- the player role already uses a player shell layered over the same presentation stack
- the backend-side `CharacterAgent` slice already exists as a separate design surface

What remains unclear is the runtime contract between:

- backend-side `CharacterAgent`
- Godot-side `CharacterActor`
- backend authority via `ESM`

Without a frozen boundary, future work can easily leak cognition into Godot, leak frame-perfect physical assumptions into backend logic, or preserve special-case player/NPC body paths.

## Goal

Define the runtime boundary for Character Actor unification in Phase 0.5:

- one shared actor substrate
- one actor-facing command surface
- explicit division between semantic intent choice, embodied execution, and authoritative settlement

This spec intentionally does not define the detailed player control feel. That belongs to the control-and-locomotion child spec.

## Scope

This spec covers:

- `CharacterActor` as the shared embodiment substrate
- autonomy modes
- actor-facing cross-boundary command contract
- interaction/focus/reacquisition rules
- command lifecycle feedback
- `CharacterAgent / CharacterActor / ESM` responsibility split
- Phase 0.5 presentation compatibility

This spec does not cover:

- full control feel tuning
- exact locomotion blend trees
- camera pitch/yaw handling details
- full Phase 1 cognition rollout

## Core Decision

Human control changes the command source, not the actor substrate.

Player-controlled actors are still embodied role characters. Human input overrides the active command source, but does not collapse the role into an empty shell or a special non-character runtime species.

## Current Runtime Layers

### Player Knight

The current player path is layered as:

```text
MainDemo
-> PlayerCharacter / CharacterBase.tscn
   -> PlayerShell.gd / CharacterBody3D
   -> CameraHolder / SpringArm3D / Camera3D
   -> Phase0PlayerBridge.gd
   -> CharacterReplica.gd
      -> KnightRoleSkin.gd
         -> crusader_knight.glb
```

### Agent Character Knights

`CharacterA` and `CharacterB` are currently:

```text
MainDemo
-> CharacterA / CharacterReplica.tscn
   -> CharacterReplica.gd
      -> KnightRoleSkin.gd

MainDemo
-> CharacterB / CharacterReplica.tscn
   -> CharacterReplica.gd
      -> KnightRoleSkin.gd
```

These current shapes are transitional. They are not intended to remain separate species.

## Target Architecture

The target runtime substrate is:

```text
CharacterActor
-> CharacterBody / locomotion shell
-> CharacterPresentation / role skin / animation / runtime sync
-> CharacterInteraction / focus / object use / dialogue trigger
-> CharacterBlackboard / observable local state
-> ControllerPort
   -> HumanController
   -> AgentControllerAdapter
   -> AwayConservativeController
   -> ScriptedTestController
```

The shared scene contract target is:

```text
CharacterActor.tscn
-> CharacterBody3D / CharacterMotor.gd
-> CameraRig optional, enabled only for the local human player
-> ControllerPort / CharacterControllerPort.gd
-> InteractionSensor / CharacterInteractionSensor.gd
-> PresentationRoot
   -> KnightRoleSkin.gd
-> FactEmitters / StateEmitters
-> Debug / Nameplate
```

`PlayerCharacter`, `CharacterA`, and `CharacterB` should converge toward this same actor shape. Their difference is controller configuration, not body or presentation substrate.

## Autonomy Modes

`CharacterActor` reserves:

```text
AutonomyMode {
  human_controlled
  agent_controlled
  idle_autonomous
  away_conservative_takeover
  scripted_test
}
```

Mode behavior:

- `human_controlled`: human input supplies active movement/action intent; `CharacterAgent` continuity hooks remain future-compatible
- `agent_controlled`: `CharacterAgent` supplies actor-facing high-level commands
- `idle_autonomous`: actor may run low-risk idle, attention, and posture continuity
- `away_conservative_takeover`: actor may issue only low-risk continuity commands
- `scripted_test`: harness/autotest supplies deterministic commands

## Shared Command Surface

The first shared actor-facing command surface is:

```text
look_at
go_to
approach
observe
interact
speak
```

Permissions vary by autonomy mode:

| Command | Human | Agent | Away Conservative |
| --- | --- | --- | --- |
| `look_at` | yes | yes | yes |
| `go_to` | yes | yes | limited |
| `approach` | yes | yes | limited |
| `observe` | yes | yes | yes |
| `interact` | yes | yes | usually no for key objects |
| `speak` | yes | yes | passive / low-risk only |

Away conservative takeover may allow:

- observe
- turn slightly
- maintain social distance
- small reposition
- passive response
- avoid immediate danger
- micro-expression and physiology continuity

Away conservative takeover must not allow:

- major dialogue progression
- revealing important secrets
- active use of key evidence
- irreversible high-risk interaction
- major dramatic choices

## Cross-Boundary Command Contract

This runtime split is frozen:

```text
CharacterGoalCommand = actor-facing backend-to-Godot contract
CharacterIntentFrame = Godot-local per-frame execution input
```

`CharacterGoalCommand` is the cross-boundary actor command surface.

`CharacterIntentFrame` is not a backend world contract. It is the local execution shape used inside Godot after controller adaptation.

### CharacterGoalCommand

```text
CharacterGoalCommand {
  actor_id
  command_type:
    look_at | go_to | approach | observe | interact | speak
  target_actor_id?
  target_object_id?
  target_position?
  verb?
  dialogue_text?
  dialogue_ref?
  gait?
  urgency?
  facing_policy?
  ttl_ms
  causation_id
  correlation_id
}
```

### CharacterIntentFrame

```text
CharacterIntentFrame {
  actor_id
  controller_source: human | agent | scripted
  look_yaw_delta
  look_pitch_delta
  desired_facing_yaw
  move_local
  gait
  action
  target_id?
  verb?
  dialogue_ref?
  dialogue_text?
  ttl_ms
  causation_id
  correlation_id
}
```

Controller mapping:

- `HumanController` maps keyboard/mouse to `CharacterIntentFrame`
- `AgentControllerAdapter` maps `CharacterGoalCommand` to `CharacterIntentFrame`
- `ScriptedTestController` emits deterministic `CharacterIntentFrame`

## AgentLocomotionAdapter

Phase 0.5 uses the confirmed hybrid mode:

```text
backend high-level goal
-> Godot AgentLocomotionAdapter local navigation/steering
-> CharacterIntentFrame
-> CharacterMotor / InteractionSensor / Presentation
```

The backend may emit high-level goals such as:

- `go_to`
- `look_at`
- `follow`
- `approach`
- `interact`
- `observe`
- `speak`

The local adapter turns those into per-frame movement/facing/action input. This preserves one shared execution substrate even when the command source is different.

## Movement Authority For Agent Goals

Phase 0.5 allows local navigation/presentation movement for non-world-changing movement goals while preserving backend authority for world-changing outcomes.

Allowed locally:

- walking toward a remembered or currently perceived location
- approach/search movement
- turning toward a target
- keeping social distance
- patrol or small repositioning

Still backend-authoritative:

- picking up or using an object
- opening or locking doors
- entering restricted spaces when that restriction matters
- relationship or dialogue-commitment consequences
- any object/environment/world state change

Memory may motivate approach/search. Memory alone must not authorize final interaction.

## Interaction Ownership

Interaction is actor-owned, not player-script-owned and not direct-agent-owned.

`CharacterInteractionSensor` owns:

- forward ray or cone query
- proximity overlap query
- line-of-sight check
- reach/path feasibility check
- focus candidate scoring
- current `FocusState`

Shared reachability rules:

- maximum interaction distance
- line-of-sight requirement
- target interactable state
- backend authority result

`FocusState` shape:

```text
FocusState {
  actor_id
  target_id
  target_type: actor | object | zone
  confidence
  distance
  line_of_sight
  resolver_source: camera_ray | perception_cone | goal_target | proximity
}
```

Source-specific focus resolution:

- human: camera ray priority, proximity fallback, UI highlight
- agent: goal target priority, private perceived targets, perception cone, path/reachability

Hard focus rules:

- human focus may use camera ray because the local player has a camera
- agent focus must not fake a camera ray
- both sources must output `FocusState`
- neither source may bypass focus and submit arbitrary interaction targets
- Godot focus is candidate/display state, not world truth

## Eligibility, Feasibility, And Authority

These checks must stay split.

### Semantic Eligibility Check

Owned by backend / `CharacterAgent`.

Question answered:

```text
Is this target meaningful, known enough, relevant enough, and worth pursuing from the actor's private state?
```

Semantic eligibility may authorize pursuit. It does not authorize final execution.

### Embodied Eligibility / Feasibility Check

Owned by Godot / `CharacterActor`.

Question answered:

```text
Can this body currently see, face, reach, path toward, or physically perform the command?
```

Execution requires local embodied gates such as:

```text
Eligibility Gate:
  target is in actor's perceived/focus/reacquired local target set
  target type supports the requested verb
  target is not hidden from this actor

Embodiment Gate:
  actor is in range
  line of sight or reach path is valid
  facing/focus is acceptable
```

Embodied feasibility may authorize a local execution attempt. It does not authorize world success.

### Authority Resolution Check

Owned by backend / `ESM`.

Question answered:

```text
Can this world-changing result actually become true?
```

World-changing actions still require backend authority.

## Interaction Fairness

`target_id` is a request, not authority.

Spec rule:

```text
Agent target_id is a request, not authority.
AgentControllerAdapter must validate target_id against actor-local embodied eligibility before acting.
Godot must not execute an agent command against a target that the actor cannot currently perceive, remember-validly, or reacquire.
```

Human eligibility comes from:

- camera ray hit
- proximity fallback
- line of sight
- interaction distance
- focus UI state

Agent eligibility comes from:

- `CharacterAgent L1` private perceived targets
- valid memory that motivates search or approach
- current perception cone / line of sight
- proximity and reachability
- embodied reacquisition before final interaction

This prevents both player and agent from interacting through walls or from acting on arbitrary target IDs.

## Speak As Embodied Action

`speak` belongs in the actor command surface, but `CharacterActor` must not generate dialogue content.

Responsibilities:

- `CharacterAgent` / `DialogueService`: dialogue text, addressee, communicative intent, optional role-state hint
- `CharacterActor`: focus toward addressee, play speech embodiment, trigger voice/stub playback, and emit local role/auditory facts

Execution:

```text
AgentControllerAdapter receives speak
-> sets focus target
-> requests facing toward target
-> emits CharacterIntentFrame(action="speak")
-> CharacterPresentation plays speak animation
-> SpatialVoiceController plays voice/stub
-> L1 emits auditory_fact + role_state_fact
```

## Human-Like Agent Embodiment Rules

Agent-controlled actors must behave like embodied characters, not omniscient API clients.

Rules:

1. Remembered targets can motivate pursuit, not final execution.
2. Final interaction requires current embodied reacquisition.
3. Uncertain memory produces search, observe, or ask behavior, not direct object use.
4. Failed reacquisition feeds back into `CharacterAgent L1/L2`.
5. Agent commands remain interruptible and observable.

Example:

```text
Agent remembers obj_letter at table.
L3 selects inspect_object.
L4 emits approach/search command.
Godot CharacterActor moves to table.
InteractionSensor searches with cone/ray/proximity.
If obj_letter is reacquired:
    submit interact_intent
If not:
    emit command_failed(target_not_reacquired)
    CharacterAgent L2 updates uncertainty
```

## Command Lifecycle Feedback

Every agent-originated goal command should report lifecycle status back through the event path.

Reserved statuses:

```text
queued
active
accepted_by_actor_adapter
semantic_target_missing
embodied_target_not_visible
embodied_out_of_range
recovering_approach
recovering_turn
submitted_to_authority
succeeded
failed
authority_rejected
completed
expired
interrupted
```

Reserved failure reasons:

```text
target_missing
target_not_perceived
target_not_eligible
target_not_visible
target_out_of_range
target_unreachable
lost_line_of_sight
authority_rejected
timeout
interrupted_by_higher_priority
```

Feedback route:

```text
CharacterActor command status
-> L6 event bus / structured result
-> CharacterAgent L1 private snapshot
-> CharacterAgent L2 interpretation update
```

## Runtime Boundary Summary

End-to-end target flow:

```text
System L1 facts
-> L6 delivery infrastructure
-> CharacterAgent L1 private snapshot
-> CharacterAgent L2 subjective interpretation
-> CharacterAgent L3 candidate generation + triple filter
-> CharacterAgent L4 actor-facing output
-> CharacterGoalCommand
-> Godot CharacterActor ControllerAdapter
-> CharacterIntentFrame
-> Embodied Eligibility / Feasibility Check
-> CharacterMotor / InteractionSensor / Presentation
-> ESM / authority resolution for world-changing actions
-> result facts back through L6
-> CharacterAgent L1/L2 update
```

Layer meanings:

```text
System L1 = world / embodied / observability fact production and local execution facts
System L6 = cross-layer infrastructure, including routing, projection, audit, replay, websocket ingress/egress, envelopes, and delivery adapters
CharacterAgent L1 = private character perception intake and snapshot
CharacterAgent L2 = subjective interpretation
CharacterAgent L3 = intent selection / planning
CharacterAgent L4 = actor-facing execution output adaptation
Godot CharacterActor = local physics, camera, interaction, animation, voice, and presentation substrate
```

Core boundary rules:

```text
System L1 does not decide meaning.
CharacterAgent L2/L3 does not invent physical observability.
L6 does not become a perception layer.
Godot does not become the character brain.
Backend does not pretend to know frame-perfect LOS/collision without Godot/System L1 facts.
```

## Phase 0.5 Presentation Compatibility

Phase 0.5 uses:

```text
CharacterPresentation -> KnightRoleSkin direct animation / motor sync
```

`KnightRoleSkin` remains the required Phase 0.5 role presentation asset.

Phase 1 target remains:

```text
CharacterAgent L4
-> FACS/SACS Planner
-> Embodiment Binder
-> Canonical Rig
-> Asset Adapter
-> Godot Runtime Mixer
-> KnightRoleSkin / final asset
```

This runtime-boundary design must preserve that future direction without requiring full Phase 1 implementation now.

## Greybox Deprecation

`GreyboxHumanoidVisual` is deprecated for Character Actor migration.

Required direction:

- remove `GreyboxHumanoidVisual.tscn` from `CharacterReplica.tscn`
- remove greybox fallback/runtime dependencies from `CharacterReplica.gd`
- keep `KnightRoleSkin` as the required Phase 0.5 presentation asset
- if a fallback is needed, use an explicit missing-asset marker instead of a second humanoid runtime

## Acceptance Criteria

This spec is accepted when implementation can prove:

1. Player and agent characters use the same `CharacterActor` substrate conceptually and, where migration allows, in scene structure.
2. Human control changes controller source, not actor substrate.
3. `CharacterGoalCommand` is the actor-facing backend contract, while `CharacterIntentFrame` is Godot-local execution input.
4. Semantic eligibility remains in `CharacterAgent`, embodied feasibility remains in `CharacterActor`, and world-changing settlement remains in `ESM`.
5. Agent-controlled interactions require approach/reacquisition and cannot execute from `target_id` alone.
6. Failed embodied reacquisition emits structured feedback that can flow back into `CharacterAgent L1/L2`.
7. `speak` is embodied by the actor while dialogue generation remains outside `CharacterActor`.
8. `KnightRoleSkin` is the required Phase 0.5 presentation asset.
9. `GreyboxHumanoidVisual` is removed from the Character Actor migration path.
10. Existing Phase 0 verification remains green.

## Verification Plan For Implementation

Implementation should include:

- contract tests for `CharacterGoalCommand` and `CharacterIntentFrame` role separation
- tests for autonomy-mode permissions and shared command surface handling
- tests for embodied reacquisition success and failure
- tests proving agent `target_id` cannot bypass local embodied checks
- tests proving `speak` triggers focus/facing/presentation without generating text in `CharacterActor`
- static scene validation that `CharacterReplica` no longer instantiates `GreyboxHumanoidVisual`
- `python scripts/verification/harness.py --profile godot-project`
- `python scripts/verification/harness.py --profile phase0`

## Relationship To Other Specs

This spec complements:

- `docs/superpowers/specs/2026-06-11-character-agent-minimal-runtime-slice-design.md`
- `docs/superpowers/specs/2026-06-12-character-actor-control-and-locomotion-design.md`

The 2026-06-11 spec defines the minimal backend-side `CharacterAgent` slice.

This runtime-boundary spec defines how that slice is allowed to drive a shared local embodiment substrate in Godot without collapsing player and agent bodies into different runtime species.
