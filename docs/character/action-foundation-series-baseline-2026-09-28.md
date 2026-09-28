# StreetCombatDemo 动作底座 baseline（2026-09-28）

Status: `Task 1 baseline frozen; later tasks remain open`

本 baseline 以 `scenes/phase0/StreetCombatDemo.tscn` 的真实街区环境为正式动作验收入口。`scenes/integration/UnifiedCharacterActionFoundation.tscn` 只保留为窄范围 protocol/authority probe，不作为动作底座验收依据。

## Probe contract

`scripts/verification/CharacterActionFoundationBaselineProbe.gd` 每个 actor 输出以下字段：`actor_id`、`source_kind`、`state`、`clip`、`velocity_world`、`position`、`action_locked`、`root_policy`、`caller_path`。

## Caller matrix

| source_kind | caller scope | registered paths | boundary |
|---|---|---|---|
| player | StreetCombatDemo player input | `scenes/phase0/StreetCombatDemo.tscn`, `scripts/street_combat/StreetCombatDemo.gd` | ControllerPort -> Actor |
| agent | StreetCombatDemo agent and CharacterAgent execution | `scripts/verification/CharacterAgentExecutionProbe.gd`, `scripts/character/EmbodiedStateProvider.gd` | ControllerPort -> Arbiter |
| program | program/adapter intent callers | `scripts/character/AgentControllerAdapter.gd`, `scripts/character/CharacterRuntimeState.gd` | normalized intent only |
| perception | perception and visual fact readers | `scripts/character/EmbodiedStateProvider.gd`, `scripts/verification/EmbodiedSkeletalRuntimeProbe.gd` | read-only observation |
| interaction | ArchiveDoor and embodied interaction | `scripts/interaction/ArchiveDoorEmbodiedActionHost.gd`, `scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd` | semantic action request |
| authority | backend/static authority consumers | `backend/app/verification_audit.py`, `backend/tests/test_character_action_lock_rules.py`, `backend/tests/test_character_replica_convergence_static.py` | authority result/projection |
| probe | verification probes and static tests | `scripts/verification/CharacterTask45Probe.gd`, `scripts/verification/verify_street_combat.py`, `scripts/verification/tests/test_street_combat_scene.py` | evidence only |

All active `CharacterReplica` references discovered by the Task 1 scan are registered below. Test files are included because they are callers of the compatibility surface, not runtime behavior owners.

- `backend/app/verification_audit.py`
- `backend/tests/test_action_window_godot_contract_static.py`
- `backend/tests/test_character_action_lock_rules.py`
- `backend/tests/test_character_actor_autonomy_modes.py`
- `backend/tests/test_character_actor_boundary_audit.py`
- `backend/tests/test_character_actor_bridge_static.py`
- `backend/tests/test_character_actor_modes_static.py`
- `backend/tests/test_character_actor_reacquisition_runtime.py`
- `backend/tests/test_character_actor_scene_convergence_static.py`
- `backend/tests/test_character_actor_schema_static.py`
- `backend/tests/test_character_controller_boundary_static.py`
- `backend/tests/test_character_debug_toggle_static.py`
- `backend/tests/test_character_final_actor_contracts_static.py`
- `backend/tests/test_character_locomotion_motor_ownership_guard_static.py`
- `backend/tests/test_character_motion_composition_contract.py`
- `backend/tests/test_character_motion_state_static.py`
- `backend/tests/test_character_motor_ownership_audit.py`
- `backend/tests/test_character_motor_static_contract.py`
- `backend/tests/test_character_near_term_presentation_contract_static.py`
- `backend/tests/test_character_presentation_asset_resolver_static.py`
- `backend/tests/test_character_replica_convergence_static.py`
- `backend/tests/test_character_runtime_boundary_static.py`
- `backend/tests/test_character_runtime_feedback_static.py`
- `backend/tests/test_character_runtime_state_extraction_static.py`
- `backend/tests/test_character_shared_ingress_static.py`
- `backend/tests/test_character_task45_behavior.py`
- `backend/tests/test_embodied_skeletal_debug_replay_pipeline.py`
- `backend/tests/test_focus_visualization_static.py`
- `backend/tests/test_obj_archive_door_embodied_local_static.py`
- `backend/tests/test_player_combat_action_static.py`
- `backend/tests/test_siming_heavenly_godot_static.py`
- `backend/tests/test_tts_service.py`
- `backend/tests/test_verification_audit.py`
- `backend/tests/test_visual_fact_pipeline.py`
- `backend/tests/test_ws_protocol.py`
- `scenes/integration/Unified3DIntegrationValidation.tscn`
- `scenes/integration/UnifiedCharacterActionFoundation.tscn`
- `scenes/phase0/CharacterAgentExecutionProbeHost.tscn`
- `scenes/phase0/CharacterBase.tscn`
- `scenes/phase0/CharacterReplica.tscn`
- `scenes/phase0/StreetCombatDemo.tscn`
- `scenes/phase0/ValidationCharacterReplica.tscn`
- `scenes/phase0/ValidationPlayerShell.tscn`
- `scripts/character/CharacterReplica.gd`
- `scripts/character/EmbodiedSkeletalStateProvider.gd`
- `scripts/character/EmbodiedStateProvider.gd`
- `scripts/character/GenericRoleSkin.gd`
- `scripts/interaction/ArchiveDoorEmbodiedActionHost.gd`
- `scripts/phase0/MainDemoController.gd`
- `scripts/player/PlayerShell.gd`
- `scripts/presentation/character/CharacterReplica.gd`
- `scripts/verification/CharacterAgentExecutionProbe.gd`
- `scripts/verification/CharacterTask45Probe.gd`
- `scripts/verification/EmbodiedSkeletalRuntimeProbe.gd`
- `scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd`
- `scripts/verification/tests/test_character_action_foundation_progressive_replacement.py`
- `scripts/verification/tests/test_character_agent_execution_probe_static.py`
- `scripts/verification/tests/test_character_base_unification.py`
- `scripts/verification/tests/test_evidence_path_migration.py`
- `scripts/verification/tests/test_phase0_correlated_ack_contract.py`
- `scripts/verification/tests/test_street_combat_scene.py`
- `scripts/verification/verify_actor_local_perception.py`
- `scripts/verification/verify_autonomous_social_contact.py`
- `scripts/verification/verify_character_agent_execution.py`
- `scripts/verification/verify_embodied_skeletal_debug_replay_pipeline.py`
- `scripts/verification/verify_phase0.py`
- `scripts/verification/verify_siming_resource_staging.py`
- `scripts/verification/verify_unified_character_action_foundation.py`

## Baseline command

```powershell
$env:PARALLS_STREET_PROBE = '1'
D:\godot\Godot_v4.6.3-stable_win64.exe --headless --path D:\Users\User\Documents\paralls-phase-0-demo --scene res://scenes/phase0/StreetCombatDemo.tscn --quit-after 300 --render-thread safe --rendering-method gl_compatibility
```

Fresh baseline status: the direct Godot command exited `0` and emitted all three `character_action_foundation_baseline` actor snapshots. It confirmed three qualified skeletons, idle/walk/attack clip availability for all three packages, and `environment=true:collision=true:navigation=true` with 42 baked navigation polygons. This probe does not yet exercise all six states as transitions or live authority.

## Static ownership findings

- `CharacterMotor.gd` is the only active owner containing `move_and_slide()`. `scripts/street_combat/streetdemo.gd` is a historical standalone demo script and is excluded from the active StreetCombatDemo caller set.
- `StreetCharacterSkin.gd` no longer has an AnimationPlayer fallback playback call; animation playback is routed through `RoleAnimationController`.
- No qualification conclusion, original `.blend`, or `session_store` was changed by Task 1.

## Live authority baseline result

`python -m pytest -q scripts/verification/tests/test_street_combat_scene.py scripts/verification/tests/test_street_combat_live.py` returned `4 passed, 1 failed`. The live backend connected and the real scene rendered all three qualified packages, but both player and agent requests were rejected with `failed_code=action_unsupported`; duplicate, stale and recovery success markers were false. This is a baseline failure to be addressed in the later authority task, not an accepted authority gate.

Task 6 migration probes registered during progressive replacement:
- `backend/tests/test_character_scene_migration.py`
- `scripts/verification/CharacterReplicaRetirementProbe.gd`
