# CharacterReplica retirement caller matrix — 2026-09-29

This is the Task 1 source inventory. `active_reference` means migration remains open; later tasks update this matrix as callers move. The JSON block is consumed by both static and Godot guards. Historical documentation is outside the active source scan.

```json
[
  {
    "caller_path": "backend/app/models/embodied_interaction.py",
    "category": "compatibility",
    "current_state": "legacy_route_literal",
    "target_entry": "CharacterActor semantic route",
    "owner_lane": "Compatibility",
    "compatibility_allowed": true,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "backend/app/verification_audit.py",
    "category": "verification",
    "current_state": "active_reference",
    "target_entry": "CharacterActor verification audit",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "backend/tests/test_action_window_godot_contract_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_actor_autonomy_modes.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_actor_boundary_audit.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_actor_bridge_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_actor_modes_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_actor_reacquisition_runtime.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_actor_scene_convergence_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_actor_schema_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_controller_boundary_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_debug_toggle_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_final_actor_contracts_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_locomotion_motor_ownership_guard_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_motion_composition_contract.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_motion_state_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_motor_ownership_audit.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_motor_static_contract.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_near_term_presentation_contract_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_presentation_asset_resolver_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_replica_convergence_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_runtime_boundary_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_runtime_feedback_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_runtime_state_extraction_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_scene_migration.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_shared_ingress_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_character_task45_behavior.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_embodied_controller_auth_ingress.py",
    "category": "migration_test",
    "current_state": "legacy_route_literal",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_embodied_interaction_contracts.py",
    "category": "migration_test",
    "current_state": "legacy_route_literal",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_embodied_skeletal_debug_replay_pipeline.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_focus_visualization_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_obj_archive_door_embodied_local_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_player_combat_action_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_siming_heavenly_godot_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_tts_service.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_verification_audit.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_visual_fact_pipeline.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "backend/tests/test_ws_protocol.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scenes/integration/Unified3DIntegrationValidation.tscn",
    "category": "scene",
    "current_state": "active_reference",
    "target_entry": "CharacterActor scene",
    "owner_lane": "Scene/player",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scenes/integration/UnifiedCharacterActionFoundation.tscn",
    "category": "scene",
    "current_state": "active_reference",
    "target_entry": "CharacterActor scene",
    "owner_lane": "Scene/player",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scenes/phase0/CharacterBase.tscn",
    "category": "scene",
    "current_state": "active_reference",
    "target_entry": "CharacterActor scene",
    "owner_lane": "Scene/player",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scenes/phase0/CharacterReplica.tscn",
    "category": "compatibility",
    "current_state": "compatibility_shell",
    "target_entry": "CharacterActor scene or forwarding shell",
    "owner_lane": "Compatibility",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scenes/phase0/ValidationCharacterReplica.tscn",
    "category": "compatibility",
    "current_state": "compatibility_shell",
    "target_entry": "CharacterActor scene or forwarding shell",
    "owner_lane": "Compatibility",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scenes/phase0/ValidationPlayerShell.tscn",
    "category": "scene",
    "current_state": "active_reference",
    "target_entry": "CharacterActor scene",
    "owner_lane": "Scene/player",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/character/CharacterReplica.gd",
    "category": "compatibility",
    "current_state": "compatibility_shell",
    "target_entry": "CharacterActor scene or forwarding shell",
    "owner_lane": "Compatibility",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scripts/character/EmbodiedSkeletalStateProvider.gd",
    "category": "embodied",
    "current_state": "active_reference",
    "target_entry": "CharacterActor embodied entry",
    "owner_lane": "Embodied/agent",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/character/EmbodiedStateProvider.gd",
    "category": "embodied",
    "current_state": "active_reference",
    "target_entry": "CharacterActor embodied entry",
    "owner_lane": "Embodied/agent",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/character/GenericRoleSkin.gd",
    "category": "comment_only",
    "current_state": "comment_only",
    "target_entry": "CharacterActor documentation",
    "owner_lane": "Contract",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/interaction/ArchiveDoorEmbodiedActionHost.gd",
    "category": "interaction",
    "current_state": "active_reference",
    "target_entry": "CharacterActor capability entry",
    "owner_lane": "Embodied/agent",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/phase0/MainDemoController.gd",
    "category": "player",
    "current_state": "active_reference",
    "target_entry": "CharacterActor player entry",
    "owner_lane": "Scene/player",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/player/PlayerShell.gd",
    "category": "player",
    "current_state": "active_reference",
    "target_entry": "CharacterActor player entry",
    "owner_lane": "Scene/player",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/presentation/character/CharacterReplica.gd",
    "category": "compatibility",
    "current_state": "compatibility_shell",
    "target_entry": "CharacterActor scene or forwarding shell",
    "owner_lane": "Compatibility",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scripts/street_combat/StreetCombatDemo.gd",
    "category": "verification",
    "current_state": "probe_reference",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/CharacterReplicaRetirementProbe.gd",
    "category": "migration_test",
    "current_state": "explicit_migration_guard",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/EmbodiedActionPlaybackProbe.gd",
    "category": "migration_test",
    "current_state": "explicit_migration_guard",
    "target_entry": "CharacterActor semantic route",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/EmbodiedSkeletalRuntimeProbe.gd",
    "category": "verification",
    "current_state": "active_reference",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd",
    "category": "verification",
    "current_state": "active_reference",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/tests/test_character_action_foundation_progressive_replacement.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scripts/verification/tests/test_character_agent_execution_probe_static.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scripts/verification/tests/test_character_base_unification.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scripts/verification/tests/test_evidence_path_migration.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scripts/verification/tests/test_phase0_correlated_ack_contract.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scripts/verification/tests/test_street_combat_scene.py",
    "category": "migration_test",
    "current_state": "migration_assertion",
    "target_entry": "CharacterActor assertions",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py"
  },
  {
    "caller_path": "scripts/verification/verify_actor_local_perception.py",
    "category": "verification",
    "current_state": "active_reference",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/verify_autonomous_social_contact.py",
    "category": "verification",
    "current_state": "active_reference",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/verify_character_agent_execution.py",
    "category": "verification",
    "current_state": "active_reference",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/verify_character_replica_retirement.py",
    "category": "migration_test",
    "current_state": "explicit_migration_guard",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Contract",
    "compatibility_allowed": true,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/verify_embodied_skeletal_debug_replay_pipeline.py",
    "category": "verification",
    "current_state": "active_reference",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/verify_phase0.py",
    "category": "verification",
    "current_state": "active_reference",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/verify_siming_resource_staging.py",
    "category": "verification",
    "current_state": "active_reference",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  },
  {
    "caller_path": "scripts/verification/verify_unified_character_action_foundation.py",
    "category": "verification",
    "current_state": "active_reference",
    "target_entry": "CharacterActor runtime probe",
    "owner_lane": "Authority/evidence",
    "compatibility_allowed": false,
    "evidence_command": "python scripts/verification/harness.py --profile character-replica-retirement"
  }
]
```
