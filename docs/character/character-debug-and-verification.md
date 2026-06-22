# Character Debug And Verification

This document records how to verify and debug the shared `CharacterActor` stack in the Phase 0 repository.

## Primary Verification Layers

### Static Tests

Useful focused tests include:

- `backend/tests/test_character_actor_modes_static.py`
- `backend/tests/test_character_controller_boundary_static.py`
- `backend/tests/test_character_runtime_boundary_static.py`
- `backend/tests/test_character_runtime_feedback_static.py`
- `backend/tests/test_character_near_term_presentation_contract_static.py`
- `backend/tests/test_character_presentation_modifier_static.py`
- `backend/tests/test_character_asset_contract_static.py`
- `backend/tests/test_character_asset_lookup_readiness_static.py`
- `backend/tests/test_character_locomotion_motor_ownership_guard_static.py`
- `backend/tests/test_player_combat_action_static.py`
- `backend/tests/test_phase0_player_command_relay_static.py`
- `backend/tests/test_main_demo_debug_noise_static.py`
- `backend/tests/test_knight_locomotion_pose_refinement_static.py`
- `backend/tests/test_player_control_static_contract.py`

### Harness Profiles

Useful harness profiles:

- `python scripts/verification/harness.py --profile docs`
- `python scripts/verification/harness.py --profile godot-project`
- `python scripts/verification/harness.py --profile phase0`

### Observatory Verification

The repo now also carries a developer-only `Character Director Observatory`.

It is intentionally separate from the old `DebugOverlay` path:

- `DebugOverlay.gd` remains the narrow log-oriented trace surface
- the observatory is the structured dramatic inspection surface

Current backend observatory projection files:

- `backend/app/models/observatory.py`
- `backend/app/services/character_agent_debug_projection.py`
- `backend/app/services/siming_debug_projection.py`
- `backend/app/services/world_outcome_debug_projection.py`
- `backend/app/services/script_beat_projection.py`

Current runtime observatory owners:

- `backend/app/character_agent/runtime/runtime_loop.py`
- `backend/app/services/siming_runtime.py`
- `backend/app/services/siming_event_pipeline.py`
- `backend/app/main.py` only drains and delivers owner-emitted records

Current Godot observatory files:

- `scripts/ui/CharacterDirectorState.gd`
- `scripts/ui/ActorStateTags.gd`
- `scripts/ui/RelationshipOverlay.gd`
- `scripts/ui/CharacterObserverPanel.gd`
- `scripts/ui/DirectorMonitorPanel.gd`
- `scripts/ui/SimingDirectorBoard.gd`
- `scripts/ui/ScriptTimelinePanel.gd`
- `scripts/ui/DialogueSceneLedger.gd`
- `scripts/ui/WorldOutcomeTrace.gd`
- `scripts/ui/ObservatoryInputController.gd`
- `scenes/phase0/ObservatoryRoot.tscn`

Current observatory message families:

- `character_agent_debug_snapshot`
- `character_agent_debug_event`
- `siming_debug_snapshot`
- `siming_debug_event`
- `world_outcome_trace`
- `script_beat_event`

Current observatory controls:

- `F6` master toggle
- `F7` director-mode toggle
- `F8` script-mode toggle
- `Tab` / `Shift+Tab` actor cycling
- `Space` freeze
- `Esc` unfreeze

Current developer-only / hidden-by-default rules:

- Godot-side observatory state starts disabled
- backend-side observatory websocket family is now delivered on the normal developer runtime path by default
- developer visibility still remains hidden-by-default and requires explicit `F6/F7/F8` activation in-scene

Current observatory runtime-verification files:

- `scenes/phase0/CharacterDirectorObservatoryProbe.tscn`
- `scripts/verification/CharacterDirectorObservatoryProbe.gd`
- `scripts/verification/verify_character_director_observatory.py`

Current observatory runtime proof:

- `python scripts/verification/verify_character_director_observatory.py`
- `python scripts/verification/verify_character_agent_execution.py`
- `python scripts/verification/verify_phase0.py`

These runtime verifiers now pre-run Godot import for the active worktree before launching the scene/probe, so strict runtime validation does not fail only because `.godot/imported` cache files have not yet been generated in the current worktree.

## Useful Runtime Trace Messages

The following log families are useful during actor debugging:

- `global_input:*`
- `global_unhandled_input:*`
- `role_action_overlay:*`
- `character_actor_status:*`
- `player_root_motion_step:*`

## Debug Overlay

`DebugOverlay.gd` currently promotes the remaining high-signal combat-trace lines into a dedicated trace section so they are easier to inspect without bringing back the older mouse-event migration noise.

## Typical Layered Debug Order

For a click-triggered combat issue:

1. `global_input:*`
2. static relay/bridge coverage in `backend/tests/test_player_combat_action_static.py`
3. `role_action_overlay:*`
4. visible role / weapon result

For a locomotion issue:

1. raw local input / `move_local`
2. `CharacterIntentFrame`
3. `CharacterMotor`
4. normalized local motion-state publication
5. `KnightRoleSkin` motion profile
6. final visible movement

For a “input triggered but visible result is weak” issue:

1. confirm shell event reached `PlayerShell`
2. confirm `Phase0PlayerCommandRelay` routed shell commands to bridge callable adapter methods
3. confirm `Phase0PlayerBridge` translated callable adapter input into actor-facing action or sync state
4. confirm `CharacterReplica` accepted or emitted runtime action state
5. confirm `CharacterRuntimeFeedback` owns nameplate/combat feedback when the issue is visible feedback
6. confirm `KnightRoleSkin` built presentation or modifier input
7. confirm `KnightCombatModifier` applied post-animation correction
8. only then inspect mesh/bone/artifact specifics

## Important Current Lessons

- high-volume shell / bridge mouse logs are intentionally trimmed from default debug surfaces
- bone-index validity does not prove final visible pose
- final reliable combat embodiment may need post-animation correction
- test scenes should suppress unrelated actor noise when debugging the player path

## Recommended Future Direction

That longer-term direction has now started landing: debug output is controlled through explicit debug/harness toggles on the shared bus and verification launchers, instead of being treated as permanently always-on default runtime noise.

## Current Verification Baseline

After the 2026-06-15 optimization convergence pass, the minimum useful verification stack is:

1. focused actor static tests
2. `python scripts/verification/harness.py --profile docs`
3. `python scripts/verification/harness.py --profile godot-project`
4. `python scripts/verification/harness.py --profile phase0`

Do not claim runtime completion from static tests alone.

Useful focused observatory tests include:

- `backend/tests/test_observatory_models.py`
- `backend/tests/test_character_agent_debug_projection.py`
- `backend/tests/test_siming_debug_projection.py`
- `backend/tests/test_world_outcome_debug_projection.py`
- `backend/tests/test_script_beat_projection.py`
- `backend/tests/test_observatory_message_delivery_static.py`
- `backend/tests/test_character_director_state_static.py`
- `backend/tests/test_actor_state_tags_static.py`
- `backend/tests/test_relationship_overlay_static.py`
- `backend/tests/test_character_observer_panel_static.py`
- `backend/tests/test_director_monitor_panel_static.py`
- `backend/tests/test_siming_director_board_static.py`
- `backend/tests/test_script_timeline_panel_static.py`
- `backend/tests/test_dialogue_scene_ledger_static.py`
- `backend/tests/test_observatory_input_controller_static.py`
- `backend/tests/test_observatory_scene_mount_static.py`
- `backend/tests/test_verification_audit.py`
- `scripts/verification/tests/test_character_agent_execution_probe_static.py`
- `scripts/verification/tests/test_character_agent_execution_verify.py`
