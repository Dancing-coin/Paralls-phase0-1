# CharacterReplica retirement report (2026-09-29)

final_state: pending_verification

## Zero caller gate

The following are the target zero-caller gate values; fresh runtime evidence has not yet established them. The report must not be treated as a completion claim until the retirement harness passes.

- active_scene_instances=0
- runtime_replica_lookups=0
- compatibility_call_count=0
- direct_body_writers_outside_motor=0
- direct_animation_writers_outside_controller=0
- provider_lookups=0
- backend_production_references=0
- runtime_script_references=0

## Evidence

```text
python scripts/verification/harness.py --profile character-replica-retirement
python -m pytest -q backend/tests/test_character_replica_convergence_static.py backend/tests/test_character_actor_boundary_audit.py
```

source_digest: `3e0cce9e71092ceefe37b733f7fce574c2e46fcd343e124ed50fbc21bb708df9`
matrix_digest: `66c63f6f3a118a34b5e4c07a5ae729b3091132248f6bf23660a771e2d11a54a6`

## Caller disposition

| Previous caller | Actor entry point | Evidence | Final state |
|---|---|---|---|
| `backend/app/models/embodied_interaction.py` | `embodied_controller_v1` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `backend/app/verification_audit.py` | `CharacterActor verification audit` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `backend/tests/test_action_window_godot_contract_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_actor_autonomy_modes.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_actor_boundary_audit.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_actor_bridge_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_actor_caller_migration_static.py` | `CharacterActor assertions` | `python -m pytest -q backend/tests/test_character_actor_caller_migration_static.py` | retired |
| `backend/tests/test_character_actor_modes_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_actor_reacquisition_runtime.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_actor_scene_convergence_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_actor_schema_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_controller_boundary_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_debug_toggle_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_final_actor_contracts_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_locomotion_motor_ownership_guard_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_motion_composition_contract.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_motion_state_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_motor_ownership_audit.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_motor_static_contract.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_near_term_presentation_contract_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_presentation_asset_resolver_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_replica_convergence_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_runtime_boundary_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_runtime_feedback_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_runtime_state_extraction_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_scene_migration.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_shared_ingress_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_character_task45_behavior.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_embodied_controller_auth_ingress.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_embodied_interaction_contracts.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_embodied_skeletal_debug_replay_pipeline.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_focus_visualization_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_obj_archive_door_embodied_local_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_player_combat_action_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_siming_heavenly_godot_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_tts_service.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_verification_audit.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_visual_fact_pipeline.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `backend/tests/test_ws_protocol.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scenes/integration/Unified3DIntegrationValidation.tscn` | `CharacterActor scene` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scenes/integration/UnifiedCharacterActionFoundation.tscn` | `CharacterActor scene` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scenes/phase0/CharacterBase.tscn` | `CharacterActor scene` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scenes/phase0/CharacterReplica.tscn` | `CharacterActor scene or forwarding shell` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scenes/phase0/ValidationCharacterReplica.tscn` | `CharacterActor scene or forwarding shell` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scenes/phase0/ValidationPlayerShell.tscn` | `CharacterActor scene` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/character/CharacterReplica.gd` | `CharacterActor scene or forwarding shell` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scripts/character/EmbodiedSkeletalStateProvider.gd` | `CharacterActor embodied entry` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/character/EmbodiedStateProvider.gd` | `CharacterActor embodied entry` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/character/GenericRoleSkin.gd` | `CharacterActor documentation` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/interaction/ArchiveDoorEmbodiedActionHost.gd` | `CharacterActor capability entry` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/phase0/MainDemoController.gd` | `CharacterActor player entry` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/player/PlayerShell.gd` | `CharacterActor player entry` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/presentation/character/CharacterReplica.gd` | `CharacterActor scene or forwarding shell` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scripts/street_combat/StreetCombatDemo.gd` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/CharacterReplicaForwardingProbe.gd` | `CharacterActor actor-only verification probe (retire in Task 7)` | `python -m pytest -q backend/tests/test_character_replica_forwarding_contract.py` | retired |
| `scripts/verification/CharacterReplicaRetirementProbe.gd` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/EmbodiedActionPlaybackProbe.gd` | `CharacterActor semantic route` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/EmbodiedSkeletalRuntimeProbe.gd` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/tests/test_character_action_foundation_progressive_replacement.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scripts/verification/tests/test_character_agent_execution_probe_static.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scripts/verification/tests/test_character_base_unification.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scripts/verification/tests/test_evidence_path_migration.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scripts/verification/tests/test_phase0_correlated_ack_contract.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scripts/verification/tests/test_street_combat_scene.py` | `CharacterActor assertions` | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | retired |
| `scripts/verification/verify_actor_local_perception.py` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/verify_autonomous_social_contact.py` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/verify_character_agent_execution.py` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/verify_character_replica_retirement.py` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/verify_embodied_skeletal_debug_replay_pipeline.py` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/verify_phase0.py` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/verify_siming_resource_staging.py` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |
| `scripts/verification/verify_unified_character_action_foundation.py` | `CharacterActor runtime probe` | `python scripts/verification/harness.py --profile character-replica-retirement` | retired |

Compatibility shell files remain in the repository for Task 8 deletion review. They are not active runtime callers and are excluded from this report’s zero-caller counters.
