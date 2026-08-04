from pathlib import Path


def test_default_scene_letter_is_a_reviewed_authority_owned_affordance_fixture() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bridge_source = (project_root / "scripts" / "interaction" / "DefaultSceneLetterAffordanceBridge.gd").read_text(encoding="utf-8")
    generic_bridge_source = (project_root / "scripts" / "interaction" / "ReviewedSceneAffordanceBridge.gd").read_text(encoding="utf-8")
    main_scene = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    object_scene = (project_root / "scenes" / "phase0" / "InteractiveObject.tscn").read_text(encoding="utf-8")

    assert "ReviewedSceneAffordanceBridge.gd" in main_scene
    assert "extends DefaultSceneLetterAffordanceBridge" in generic_bridge_source
    assert "never infers an affordance" in generic_bridge_source
    assert "metadata/grounding_refs" in object_scene
    assert "InteractionCollider" in object_scene
    assert "ApproachStance" in object_scene
    assert "ObservationAnchor" in object_scene
    assert '"authority_policy:esm_inspect_letter:v1"' in bridge_source
    assert '"execution_profile:inspect:authority_only:v1"' in bridge_source
    assert '"object_state_result"' in bridge_source
    assert '"constraint_state_result"' not in bridge_source
    assert "resolve_interaction" in bridge_source
    assert "_refresh_local_occupancy(target)" in bridge_source
    assert '"local_observation:%s" % object_id' in bridge_source
    assert "world_truth" not in bridge_source


def test_main_demo_requires_the_reviewed_binding_before_sending_letter_intent() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")

    assert "_has_reviewed_default_scene_affordance(target_object_id, interaction_type)" in controller_source
    assert "phase0_interact_registry_rejected" in controller_source
    assert "emit_interact_intent(target_object_id, interaction_type)" in controller_source


def test_main_demo_registers_plaque_through_the_same_reviewed_bridge_contract() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bridge_source = (project_root / "scripts" / "interaction" / "DefaultSceneLetterAffordanceBridge.gd").read_text(encoding="utf-8")
    main_scene = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    esm_source = (project_root / "backend" / "app" / "services" / "esm_service.py").read_text(encoding="utf-8")
    extractor_source = (project_root / "scripts" / "l1" / "space" / "SceneSpaceModelExtractor.gd").read_text(encoding="utf-8")

    assert 'object_id = "obj_plaque"' in main_scene
    assert 'affordance_id = "affordance:obj_plaque:inspect"' in main_scene
    assert 'policy_ref = "authority_policy:esm_inspect_plaque:v1"' in main_scene
    assert "metadata/grounding_refs = PackedStringArray(\"collider:obj_plaque:body\"" in main_scene
    assert "handles_interaction" in bridge_source
    assert "default_scene_affordance_bridges" in controller_source
    assert '"obj_plaque"' in esm_source
    assert '"unsupported_object"' in esm_source
    assert 'str(node.get_meta("entity_ref", "")).strip_edges()' in extractor_source
    assert 'node.get("object_id")' in extractor_source


def test_main_demo_registers_switch_as_an_explicit_press_fixture() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bridge_source = (project_root / "scripts" / "interaction" / "DefaultSceneLetterAffordanceBridge.gd").read_text(encoding="utf-8")
    main_scene = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    esm_source = (project_root / "backend" / "app" / "services" / "esm_service.py").read_text(encoding="utf-8")
    main_source = (project_root / "backend" / "app" / "main.py").read_text(encoding="utf-8")

    assert 'object_id = "obj_lamp_switch"' in main_scene
    assert 'affordance_id = "affordance:obj_lamp_switch:press"' in main_scene
    assert 'primary_interaction_type = "press"' in main_scene
    assert 'policy_ref = "authority_policy:esm_press_lamp_switch:v1"' in main_scene
    assert "metadata/grounding_refs = PackedStringArray(\"collider:obj_lamp_switch:body\"" in main_scene
    assert "default_interaction_type" in bridge_source
    assert "primary_interaction_type" in bridge_source
    assert "action_semantic" in bridge_source
    assert "_default_reviewed_interaction_type" in controller_source
    assert '"obj_lamp_switch"' in esm_source
    assert 'machine_id=str(interaction_policy["machine_id"])' in main_source


def test_main_demo_registers_door_as_an_explicit_open_fixture() -> None:
    project_root = Path(__file__).resolve().parents[2]
    main_scene = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    esm_source = (project_root / "backend" / "app" / "services" / "esm_service.py").read_text(encoding="utf-8")
    bridge_source = (project_root / "scripts" / "interaction" / "ArchiveDoorEmbodiedAffordanceBridge.gd").read_text(encoding="utf-8")

    assert 'object_id = "obj_archive_door"' in main_scene
    assert 'path="res://scenes/phase0/ArchiveDoorPhysical.tscn"' in main_scene
    assert 'path="res://scripts/interaction/ArchiveDoorEmbodiedAffordanceBridge.gd"' in main_scene
    assert 'instance=ExtResource("139_archive_door_physical")' in main_scene
    assert 'script = ExtResource("140_archive_door_bridge")' in main_scene
    assert "$DefaultSceneArchiveDoorAffordanceBridge" in controller_source
    assert '"obj_archive_door"' in esm_source
    assert 'const AFFORDANCE_ID := "affordance:obj_archive_door:open"' in bridge_source
    assert '["approach_stance", "contact", "observation"]' in bridge_source
    assert 'interaction_type == "open"' in bridge_source


def test_main_demo_registers_worktable_as_a_stateful_single_actor_use_fixture() -> None:
    project_root = Path(__file__).resolve().parents[2]
    main_scene = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    esm_source = (project_root / "backend" / "app" / "services" / "esm_service.py").read_text(encoding="utf-8")

    assert 'object_id = "obj_worktable"' in main_scene
    assert 'affordance_id = "affordance:obj_worktable:use_surface"' in main_scene
    assert 'primary_interaction_type = "use"' in main_scene
    assert 'supported_interaction_types = PackedStringArray("use", "finish_use")' in main_scene
    assert 'default_interaction_by_state = {"ready": "use", "engaged": "finish_use"}' in main_scene
    assert 'policy_ref = "authority_policy:esm_use_worktable:v1"' in main_scene
    assert "metadata/grounding_refs = PackedStringArray(\"collider:obj_worktable:body\"" in main_scene
    assert "$DefaultSceneWorktableAffordanceBridge" in controller_source
    assert '"obj_worktable"' in esm_source


def test_main_demo_registers_observation_bench_with_authority_scoped_occupancy() -> None:
    project_root = Path(__file__).resolve().parents[2]
    main_scene = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    esm_source = (project_root / "backend" / "app" / "services" / "esm_service.py").read_text(encoding="utf-8")
    main_source = (project_root / "backend" / "app" / "main.py").read_text(encoding="utf-8")

    assert 'object_id = "obj_observation_bench"' in main_scene
    assert 'affordance_id = "affordance:obj_observation_bench:seat"' in main_scene
    assert 'primary_interaction_type = "sit"' in main_scene
    assert 'supported_interaction_types = PackedStringArray("sit", "stand")' in main_scene
    assert 'default_interaction_by_state = {"available": "sit", "occupied": "stand"}' in main_scene
    assert 'policy_ref = "authority_policy:esm_occupy_observation_bench:v1"' in main_scene
    assert "metadata/grounding_refs = PackedStringArray(\"collider:obj_observation_bench:body\"" in main_scene
    assert "$DefaultSceneObservationBenchAffordanceBridge" in controller_source
    assert '"obj_observation_bench"' in esm_source
    assert '"owner_requirement": "actor_is_owner"' in esm_source
    assert "reject_interaction_owner" in main_source
    assert 'body_state_class=str(interaction_policy.get("body_state_class", "interaction_strain"))' in main_source


def test_main_demo_registers_archive_token_as_a_backend_resolved_pickup_fixture() -> None:
    project_root = Path(__file__).resolve().parents[2]
    main_scene = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    mapper_source = (project_root / "scripts" / "player" / "PlayerIntentMapper.gd").read_text(encoding="utf-8")
    presentation_source = (project_root / "scripts" / "interaction" / "DefaultScenePickupPresentationBridge.gd").read_text(encoding="utf-8")
    policy_source = (project_root / "backend" / "app" / "services" / "default_scene_pickup_policy.py").read_text(encoding="utf-8")

    assert 'object_id = "obj_archive_token"' in main_scene
    assert 'affordance_id = "affordance:obj_archive_token:grab"' in main_scene
    assert 'intent_route = "pickup"' in main_scene
    assert 'DefaultSceneArchiveTokenPresentationBridge' in main_scene
    assert "$DefaultSceneArchiveTokenAffordanceBridge" in controller_source
    assert "emit_pickup_intent(target_object_id)" in controller_source
    assert '"intent_type": "pickup_intent"' in mapper_source
    assert "CarryPlaceMirrorConsumer" in presentation_source
    assert "authority_only" in presentation_source
    assert 'asset_ref="item:archive_token_01"' in policy_source
    assert "source_holder_ref" in policy_source
    assert "drop_target_ref" in policy_source


def test_main_demo_registers_archive_storage_chest_as_a_reviewed_retrieve_fixture() -> None:
    project_root = Path(__file__).resolve().parents[2]
    main_scene = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    mapper_source = (project_root / "scripts" / "player" / "PlayerIntentMapper.gd").read_text(encoding="utf-8")
    policy_source = (project_root / "backend" / "app" / "services" / "default_scene_pickup_policy.py").read_text(encoding="utf-8")

    assert 'object_id = "obj_archive_storage_chest"' in main_scene
    assert 'affordance_id = "affordance:obj_archive_storage_chest:retrieve"' in main_scene
    assert 'intent_route = "retrieve"' in main_scene
    assert 'policy_ref = "authority_policy:default_scene_retrieve_archive_token:v1"' in main_scene
    assert "_emit_retrieve_intent_request" in controller_source
    assert '"intent_type": "retrieve_intent"' in mapper_source
    assert "DefaultSceneRetrievePolicy" in policy_source
    assert "destination_receiver_by_actor_id" in policy_source
