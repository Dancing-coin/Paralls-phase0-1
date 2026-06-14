# Character Debug And Verification

This document records how to verify and debug the shared `CharacterActor` stack in the Phase 0 repository.

## Primary Verification Layers

### Static Tests

Useful focused tests include:

- `backend/tests/test_character_actor_modes_static.py`
- `backend/tests/test_character_controller_boundary_static.py`
- `backend/tests/test_character_runtime_boundary_static.py`
- `backend/tests/test_character_presentation_modifier_static.py`
- `backend/tests/test_character_asset_contract_static.py`
- `backend/tests/test_player_combat_action_static.py`
- `backend/tests/test_main_demo_debug_noise_static.py`
- `backend/tests/test_knight_locomotion_pose_refinement_static.py`
- `backend/tests/test_player_control_static_contract.py`

### Harness Profiles

Useful harness profiles:

- `python scripts/verification/harness.py --profile docs`
- `python scripts/verification/harness.py --profile godot-project`
- `python scripts/verification/harness.py --profile phase0`

## Useful Runtime Trace Messages

The following log families are useful during actor debugging:

- `global_input:*`
- `global_unhandled_input:*`
- `player_shell_mouse_button:*`
- `mouse_button_state:*`
- `combat_mouse_event:*`
- `player_combat_action:*`
- `role_action_overlay:*`
- `character_actor_status:*`
- `player_root_motion_step:*`

## Debug Overlay

`DebugOverlay.gd` currently promotes combat-trace-related lines into a dedicated trace section so they are easier to inspect without being drowned by unrelated runtime output.

## Typical Layered Debug Order

For a click-triggered combat issue:

1. `global_input:*`
2. `player_shell_mouse_button:*`
3. `combat_mouse_event:*`
4. `player_combat_action:*`
5. `role_action_overlay:*`
6. visible role / weapon result

For a locomotion issue:

1. raw local input / `move_local`
2. `CharacterIntentFrame`
3. `CharacterMotor`
4. `CharacterMotionState`
5. `KnightRoleSkin` motion profile
6. final visible movement

For a “input triggered but visible result is weak” issue:

1. confirm shell event reached `PlayerShell`
2. confirm `Phase0PlayerBridge` translated it into actor-facing action or sync state
3. confirm `CharacterReplica` accepted or emitted runtime action state
4. confirm `KnightRoleSkin` built presentation or modifier input
5. confirm `KnightCombatModifier` applied post-animation correction
6. only then inspect mesh/bone/artifact specifics

## Important Current Lessons

- action logs do not prove visible embodiment
- bone-index validity does not prove final visible pose
- final reliable combat embodiment may need post-animation correction
- test scenes should suppress unrelated actor noise when debugging the player path

## Recommended Future Direction

Longer-term, debug output should be controlled through explicit debug modes instead of being permanently embedded in the default runtime path.

## Current Verification Baseline

After the 2026-06-15 optimization convergence pass, the minimum useful verification stack is:

1. focused actor static tests
2. `python scripts/verification/harness.py --profile docs`
3. `python scripts/verification/harness.py --profile godot-project`
4. `python scripts/verification/harness.py --profile phase0`

Do not claim runtime completion from static tests alone.
