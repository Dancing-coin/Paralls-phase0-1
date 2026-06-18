# Character Control Chain

This document explains how control moves through the current actor stack.

## Shared Principle

All control sources should converge onto one shared actor substrate.

The three supported control sources are:

- `human_controlled`
- `agent_controlled`
- `program_controlled`

## Traveler / Human Control Path

```text
mouse / keyboard
-> PlayerShell
-> Phase0PlayerBridge
-> HumanControllerAdapter
-> CharacterControllerPort
-> CharacterIntentFrame
-> CharacterMotor
-> normalized local motion-state publication
-> CharacterReplica
-> KnightRoleSkin
-> KnightCombatModifier
-> final visible role body
```

### Main Responsibilities

- `PlayerShell.gd`
  - raw human input
  - camera/body yaw coupling
  - human-source intent-frame staging

- `Phase0PlayerBridge.gd`
  - action translation and demo/player-shell sync
  - program-entry relay surface for the shared ingress family
  - player shell <-> visible actor sync through thin actor-facing helper aliases
  - normalized intent-frame consumption through `CharacterControllerPort` helper reads rather than bridge-local dict unpacking

- `Phase0CharacterShellSync.gd`
  - thin sync helper that now prefers actor-facing embodied-control aliases
  - only falls back to older player-shell-specific method names for migration compatibility

- `Phase0ViewAnchorResolver.gd`
  - thin view/anchor helper that now prefers actor-facing embodied-control / forward aliases
  - normalized intent-frame forward fallback now routes through `CharacterControllerPort` helper reads
  - only falls back to older player-shell-specific names or wrapper camera seams for migration compatibility

- `HumanControllerAdapter.gd`
  - human-source adaptation into shared actor intent

- `CharacterControllerPort.gd`
  - normalized actor-facing intent/control shape
  - shared field-read surface for `move_local`, `gait`, `desired_facing_yaw`, and `actor_id`

- `CharacterMotor.gd`
  - locomotion truth

- `CharacterReplica.gd`
  - actor runtime shell around `CharacterRuntimeState`

- `KnightRoleSkin.gd`
  - base presentation

- `KnightCombatModifier.gd`
  - animation-post combat embodiment correction

## Agent Control Path

```text
CharacterAgent
-> CharacterGoalCommand
-> AgentControllerAdapter
-> CharacterControllerPort
-> CharacterIntentFrame
-> CharacterRuntimeState
-> CharacterMotor
-> normalized local motion-state publication
-> CharacterReplica
-> KnightRoleSkin
-> KnightCombatModifier
```

The source differs, but the lower-half actor body path should stay shared.

## Program Control Path

```text
autotest / replay / MCP / harness
-> program command input
-> ProgramControllerAdapter
-> CharacterControllerPort
-> CharacterIntentFrame
-> CharacterRuntimeState
-> CharacterMotor
-> normalized local motion-state publication
-> CharacterReplica
-> KnightRoleSkin
-> KnightCombatModifier
```

This path exists for:

- deterministic testing
- replay
- debug control
- harness verification

## Left Click Sword Swing Chain

```text
mouse button left
-> PlayerShell raw input capture
-> Phase0PlayerBridge.handle_mouse_combat_event()
-> _trigger_combat_action("sword_swing")
-> CharacterReplica.perform_action("sword_swing")
-> KnightRoleSkin sword timer
-> KnightCombatModifier sword overlay
-> final visible sword / right-arm result
```

## Right Click Shield Block Chain

```text
mouse button right
-> PlayerShell raw input capture
-> Phase0PlayerBridge.handle_mouse_combat_event()
-> _trigger_combat_action("shield_block")
-> CharacterReplica.perform_action("shield_block")
-> KnightRoleSkin shield timer
-> KnightCombatModifier shield overlay
-> final visible shield / left-arm result
```

## Locomotion Chain

```text
WASD / run / jump
-> PlayerShell human intent frame
-> HumanControllerAdapter
-> CharacterControllerPort
-> CharacterIntentFrame
-> CharacterMotor.apply_intent_frame()
-> normalized local motion-state publication
-> Phase0CharacterShellSync actor-facing helper surface
-> CharacterReplica embodied control / pose sync
-> KnightRoleSkin motion profile / locomotion refinement
-> final visible movement
```

## Practical Debug Layers

When debugging input or action problems, inspect the chain in this order:

1. `global_input:*`
2. static relay/bridge coverage in `backend/tests/test_player_combat_action_static.py`
3. `role_action_overlay:*`
4. visible body result

If the chain breaks:

- before step 2: input never reached `PlayerShell`
- before step 3: bridge/adaptation problem
- before step 4: actor/runtime or timer problem
- after step 4: presentation or modifier problem

## Why The Modifier Exists

Combat pose changes are intentionally applied after base animation evaluation.

The modifier exists because:

- writing combat pose directly in the base presentation layer can be overwritten by animation playback
- post-animation correction is the correct place for reliable final combat embodiment

## Mid-Term ControllerPort Boundary

`ControllerPort` was a Phase1-facing mid-term boundary during the near-term cleanup pass.

Current repo truth is:

- the near-term cleanup kept `PlayerShell` and `Phase0PlayerBridge` as the demo-safe seam
- Stage 2 has now landed `CharacterControllerPort`
- Stage 2 has now landed `HumanControllerAdapter`, `AgentControllerAdapter`, and `ProgramControllerAdapter`
- Stage 2 now also routes more wrapper/helper-side normalized intent reads back through `CharacterControllerPort` helper methods instead of leaving those field names spread across `PlayerShell` and `Phase0ViewAnchorResolver`
- Stage 2 now also prefers actor-facing helper aliases in `Phase0CharacterShellSync` and `Phase0ViewAnchorResolver` before falling back to older player-shell-specific naming or broader wrapper-camera fallback
- Stage 2 still keeps those older names only as thin migration-compat fallbacks, not as the preferred architecture truth
- full actor convergence is still not complete, so these seams should be treated as the first landed shared ingress family rather than the final finished architecture
