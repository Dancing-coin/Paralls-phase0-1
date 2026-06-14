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
-> CharacterIntentFrame-style adaptation
-> CharacterMotor
-> CharacterMotionState
-> CharacterReplica
-> KnightRoleSkin
-> KnightCombatModifier
-> final visible role body
```

### Main Responsibilities

- `PlayerShell.gd`
  - raw human input
  - camera/body yaw coupling
  - raw shell motion frame

- `Phase0PlayerBridge.gd`
  - action translation
  - player shell <-> visible actor sync

- `CharacterMotor.gd`
  - locomotion truth

- `CharacterReplica.gd`
  - role-runtime state

- `KnightRoleSkin.gd`
  - base presentation

- `KnightCombatModifier.gd`
  - animation-post combat embodiment correction

## Agent Control Path

```text
CharacterAgent
-> CharacterGoalCommand
-> adapter
-> CharacterIntentFrame
-> CharacterMotor
-> CharacterMotionState
-> CharacterReplica
-> KnightRoleSkin
-> KnightCombatModifier
```

The source differs, but the lower-half actor body path should stay shared.

## Program Control Path

```text
autotest / replay / MCP / harness
-> program command input
-> adapter
-> CharacterIntentFrame
-> CharacterMotor
-> CharacterMotionState
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
-> PlayerShell current_intent_frame
-> CharacterMotor.apply_intent_frame()
-> CharacterMotionState
-> CharacterReplica player control frame sync
-> KnightRoleSkin motion profile / locomotion refinement
-> final visible movement
```

## Practical Debug Layers

When debugging input or action problems, inspect the chain in this order:

1. `global_input:*`
2. `player_shell_mouse_button:*`
3. `combat_mouse_event:*`
4. `player_combat_action:*`
5. `role_action_overlay:*`
6. visible body result

If the chain breaks:

- before step 2: input never reached `PlayerShell`
- before step 4: bridge/adaptation problem
- before step 5: actor/runtime or timer problem
- after step 5: presentation or modifier problem

## Why The Modifier Exists

Combat pose changes are intentionally applied after base animation evaluation.

The modifier exists because:

- writing combat pose directly in the base presentation layer can be overwritten by animation playback
- post-animation correction is the correct place for reliable final combat embodiment
