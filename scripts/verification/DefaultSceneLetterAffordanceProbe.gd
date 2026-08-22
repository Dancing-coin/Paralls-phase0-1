extends Node

const LETTER_SCENE := preload("res://scenes/phase0/InteractiveObject.tscn")
const LETTER_BRIDGE := preload("res://scripts/interaction/DefaultSceneLetterAffordanceBridge.gd")
const PICKUP_PRESENTATION_BRIDGE := preload("res://scripts/interaction/DefaultScenePickupPresentationBridge.gd")


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var letter = LETTER_SCENE.instantiate()
	letter.name = "InteractiveObject"
	add_child(letter)
	var bridge = LETTER_BRIDGE.new()
	bridge.name = "DefaultSceneLetterAffordanceBridge"
	bridge.target_object_path = NodePath("../InteractiveObject")
	add_child(bridge)
	var plaque = LETTER_SCENE.instantiate()
	plaque.name = "InteractivePlaque"
	plaque.object_id = "obj_plaque"
	plaque.display_name = "Plaque"
	plaque.set_meta("grounding_refs", PackedStringArray([
		"collider:obj_plaque:body",
		"anchor:obj_plaque:stance",
		"anchor:obj_plaque:observation",
		"affordance:obj_plaque:inspect",
		"nav:obj_plaque:approach_footprint",
	]))
	add_child(plaque)
	var plaque_bridge = LETTER_BRIDGE.new()
	plaque_bridge.name = "DefaultScenePlaqueAffordanceBridge"
	plaque_bridge.target_object_path = NodePath("../InteractivePlaque")
	plaque_bridge.object_id = "obj_plaque"
	plaque_bridge.affordance_id = "affordance:obj_plaque:inspect"
	plaque_bridge.semantic_type = "plaque"
	plaque_bridge.semantic_tags = PackedStringArray(["plaque", "inspectable", "readable"])
	plaque_bridge.policy_ref = "authority_policy:esm_inspect_plaque:v1"
	add_child(plaque_bridge)
	var lamp_switch = LETTER_SCENE.instantiate()
	lamp_switch.name = "InteractiveLampSwitch"
	lamp_switch.object_id = "obj_lamp_switch"
	lamp_switch.display_name = "Lamp Switch"
	lamp_switch.initial_state = "idle"
	lamp_switch.set_meta("grounding_refs", PackedStringArray([
		"collider:obj_lamp_switch:body",
		"anchor:obj_lamp_switch:stance",
		"anchor:obj_lamp_switch:observation",
		"affordance:obj_lamp_switch:press",
		"nav:obj_lamp_switch:approach_footprint",
	]))
	add_child(lamp_switch)
	var lamp_switch_bridge = LETTER_BRIDGE.new()
	lamp_switch_bridge.name = "DefaultSceneLampSwitchAffordanceBridge"
	lamp_switch_bridge.target_object_path = NodePath("../InteractiveLampSwitch")
	lamp_switch_bridge.object_id = "obj_lamp_switch"
	lamp_switch_bridge.affordance_id = "affordance:obj_lamp_switch:press"
	lamp_switch_bridge.semantic_type = "lamp_switch"
	lamp_switch_bridge.semantic_tags = PackedStringArray(["switch", "pressable", "room_control"])
	lamp_switch_bridge.policy_ref = "authority_policy:esm_press_lamp_switch:v1"
	lamp_switch_bridge.supported_interaction_types = PackedStringArray(["press"])
	lamp_switch_bridge.primary_interaction_type = "press"
	lamp_switch_bridge.action_semantic = "press"
	lamp_switch_bridge.state_preconditions = PackedStringArray(["idle"])
	lamp_switch_bridge.execution_profile_ref = "execution_profile:press:authority_only:v1"
	add_child(lamp_switch_bridge)
	var archive_door = LETTER_SCENE.instantiate()
	archive_door.name = "InteractiveArchiveDoor"
	archive_door.object_id = "obj_archive_door"
	archive_door.display_name = "Archive Door"
	archive_door.initial_state = "closed"
	archive_door.set_meta("grounding_refs", PackedStringArray([
		"collider:obj_archive_door:body",
		"anchor:obj_archive_door:stance",
		"anchor:obj_archive_door:observation",
		"affordance:obj_archive_door:open_close",
		"nav:obj_archive_door:approach_footprint",
	]))
	add_child(archive_door)
	var archive_door_bridge = LETTER_BRIDGE.new()
	archive_door_bridge.name = "DefaultSceneArchiveDoorAffordanceBridge"
	archive_door_bridge.target_object_path = NodePath("../InteractiveArchiveDoor")
	archive_door_bridge.object_id = "obj_archive_door"
	archive_door_bridge.affordance_id = "affordance:obj_archive_door:open_close"
	archive_door_bridge.semantic_type = "door"
	archive_door_bridge.semantic_tags = PackedStringArray(["door", "openable", "archive_access"])
	archive_door_bridge.policy_ref = "authority_policy:esm_open_archive_door:v1"
	archive_door_bridge.supported_interaction_types = PackedStringArray(["open", "close"])
	archive_door_bridge.primary_interaction_type = "open"
	archive_door_bridge.default_interaction_by_state = {"closed": "open", "open": "close"}
	archive_door_bridge.action_semantic = "open_close"
	archive_door_bridge.state_preconditions = PackedStringArray(["closed", "open"])
	archive_door_bridge.execution_profile_ref = "execution_profile:open_close:authority_only:v1"
	add_child(archive_door_bridge)
	var worktable = LETTER_SCENE.instantiate()
	worktable.name = "InteractiveWorktable"
	worktable.object_id = "obj_worktable"
	worktable.display_name = "Worktable"
	worktable.initial_state = "ready"
	worktable.set_meta("grounding_refs", PackedStringArray([
		"collider:obj_worktable:body",
		"anchor:obj_worktable:stance",
		"anchor:obj_worktable:observation",
		"affordance:obj_worktable:use_surface",
		"nav:obj_worktable:approach_footprint",
	]))
	add_child(worktable)
	var worktable_bridge = LETTER_BRIDGE.new()
	worktable_bridge.name = "DefaultSceneWorktableAffordanceBridge"
	worktable_bridge.target_object_path = NodePath("../InteractiveWorktable")
	worktable_bridge.object_id = "obj_worktable"
	worktable_bridge.affordance_id = "affordance:obj_worktable:use_surface"
	worktable_bridge.semantic_type = "worktable"
	worktable_bridge.semantic_tags = PackedStringArray(["table", "work_surface", "single_actor_use"])
	worktable_bridge.policy_ref = "authority_policy:esm_use_worktable:v1"
	worktable_bridge.supported_interaction_types = PackedStringArray(["use", "finish_use"])
	worktable_bridge.primary_interaction_type = "use"
	worktable_bridge.default_interaction_by_state = {"ready": "use", "engaged": "finish_use"}
	worktable_bridge.action_semantic = "use_surface"
	worktable_bridge.state_preconditions = PackedStringArray(["ready", "engaged"])
	worktable_bridge.execution_profile_ref = "execution_profile:use_surface:authority_only:v1"
	add_child(worktable_bridge)
	var observation_bench = LETTER_SCENE.instantiate()
	observation_bench.name = "InteractiveObservationBench"
	observation_bench.object_id = "obj_observation_bench"
	observation_bench.display_name = "Observation Bench"
	observation_bench.initial_state = "available"
	observation_bench.set_meta("grounding_refs", PackedStringArray([
		"collider:obj_observation_bench:body",
		"anchor:obj_observation_bench:stance",
		"anchor:obj_observation_bench:observation",
		"affordance:obj_observation_bench:seat",
		"nav:obj_observation_bench:approach_footprint",
	]))
	add_child(observation_bench)
	var observation_bench_bridge = LETTER_BRIDGE.new()
	observation_bench_bridge.name = "DefaultSceneObservationBenchAffordanceBridge"
	observation_bench_bridge.target_object_path = NodePath("../InteractiveObservationBench")
	observation_bench_bridge.object_id = "obj_observation_bench"
	observation_bench_bridge.affordance_id = "affordance:obj_observation_bench:seat"
	observation_bench_bridge.semantic_type = "observation_bench"
	observation_bench_bridge.semantic_tags = PackedStringArray(["seat", "observation_bench", "single_occupant"])
	observation_bench_bridge.policy_ref = "authority_policy:esm_occupy_observation_bench:v1"
	observation_bench_bridge.supported_interaction_types = PackedStringArray(["sit", "stand"])
	observation_bench_bridge.primary_interaction_type = "sit"
	observation_bench_bridge.default_interaction_by_state = {"available": "sit", "occupied": "stand"}
	observation_bench_bridge.action_semantic = "seat_occupancy"
	observation_bench_bridge.state_preconditions = PackedStringArray(["available", "occupied"])
	observation_bench_bridge.execution_profile_ref = "execution_profile:seat_occupancy:authority_only:v1"
	add_child(observation_bench_bridge)
	var archive_token = LETTER_SCENE.instantiate()
	archive_token.name = "InteractiveArchiveToken"
	archive_token.object_id = "obj_archive_token"
	archive_token.display_name = "Archive Token"
	archive_token.initial_state = "available"
	archive_token.set_meta("grounding_refs", PackedStringArray([
		"collider:obj_archive_token:body",
		"anchor:obj_archive_token:stance",
		"anchor:obj_archive_token:observation",
		"affordance:obj_archive_token:grab",
		"nav:obj_archive_token:approach_footprint",
	]))
	add_child(archive_token)
	var archive_token_bridge = LETTER_BRIDGE.new()
	archive_token_bridge.name = "DefaultSceneArchiveTokenAffordanceBridge"
	archive_token_bridge.target_object_path = NodePath("../InteractiveArchiveToken")
	archive_token_bridge.object_id = "obj_archive_token"
	archive_token_bridge.affordance_id = "affordance:obj_archive_token:grab"
	archive_token_bridge.semantic_type = "archive_token"
	archive_token_bridge.semantic_tags = PackedStringArray(["pickup", "archive_token", "custody_only"])
	archive_token_bridge.policy_ref = "authority_policy:default_scene_pickup_archive_token:v1"
	archive_token_bridge.supported_interaction_types = PackedStringArray(["grab"])
	archive_token_bridge.primary_interaction_type = "grab"
	archive_token_bridge.action_semantic = "grab"
	archive_token_bridge.intent_route = "pickup"
	archive_token_bridge.state_preconditions = PackedStringArray(["available"])
	archive_token_bridge.execution_profile_ref = "execution_profile:grab:authority_only:v1"
	add_child(archive_token_bridge)
	var archive_token_presentation_bridge = PICKUP_PRESENTATION_BRIDGE.new()
	archive_token_presentation_bridge.name = "DefaultSceneArchiveTokenPresentationBridge"
	archive_token_presentation_bridge.target_object_path = NodePath("../InteractiveArchiveToken")
	archive_token_presentation_bridge.object_id = "obj_archive_token"
	archive_token_presentation_bridge.asset_ref = "item:archive_token_01"
	add_child(archive_token_presentation_bridge)
	var archive_storage_chest = LETTER_SCENE.instantiate()
	archive_storage_chest.name = "InteractiveArchiveStorageChest"
	archive_storage_chest.object_id = "obj_archive_storage_chest"
	archive_storage_chest.display_name = "Archive Storage Chest"
	archive_storage_chest.initial_state = "available"
	archive_storage_chest.set_meta("grounding_refs", PackedStringArray([
		"collider:obj_archive_storage_chest:body",
		"anchor:obj_archive_storage_chest:stance",
		"anchor:obj_archive_storage_chest:observation",
		"affordance:obj_archive_storage_chest:retrieve",
		"nav:obj_archive_storage_chest:approach_footprint",
	]))
	add_child(archive_storage_chest)
	var archive_storage_chest_bridge = LETTER_BRIDGE.new()
	archive_storage_chest_bridge.name = "DefaultSceneArchiveStorageChestAffordanceBridge"
	archive_storage_chest_bridge.target_object_path = NodePath("../InteractiveArchiveStorageChest")
	archive_storage_chest_bridge.object_id = "obj_archive_storage_chest"
	archive_storage_chest_bridge.affordance_id = "affordance:obj_archive_storage_chest:retrieve"
	archive_storage_chest_bridge.semantic_type = "archive_storage_chest"
	archive_storage_chest_bridge.semantic_tags = PackedStringArray(["container", "archive_storage", "retrieve_only"])
	archive_storage_chest_bridge.policy_ref = "authority_policy:default_scene_retrieve_archive_token:v1"
	archive_storage_chest_bridge.supported_interaction_types = PackedStringArray(["retrieve"])
	archive_storage_chest_bridge.primary_interaction_type = "retrieve"
	archive_storage_chest_bridge.action_semantic = "retrieve"
	archive_storage_chest_bridge.intent_route = "retrieve"
	archive_storage_chest_bridge.state_preconditions = PackedStringArray(["available"])
	archive_storage_chest_bridge.execution_profile_ref = "execution_profile:retrieve:authority_only:v1"
	add_child(archive_storage_chest_bridge)
	await get_tree().process_frame

	var initial_resolution: Dictionary = bridge.resolve_interaction("obj_letter", "inspect")
	var letter_destroy_resolution: Dictionary = bridge.resolve_interaction("obj_letter", "destroy")
	var plaque_initial_resolution: Dictionary = plaque_bridge.resolve_interaction("obj_plaque", "read")
	var lamp_switch_initial_resolution: Dictionary = lamp_switch_bridge.resolve_interaction("obj_lamp_switch", "press")
	var lamp_switch_default_interaction := lamp_switch_bridge.default_interaction_type("obj_lamp_switch")
	var archive_door_initial_resolution: Dictionary = archive_door_bridge.resolve_interaction("obj_archive_door", "open")
	var archive_door_default_interaction := archive_door_bridge.default_interaction_type("obj_archive_door")
	var worktable_initial_resolution: Dictionary = worktable_bridge.resolve_interaction("obj_worktable", "use")
	var worktable_default_interaction := worktable_bridge.default_interaction_type("obj_worktable")
	var observation_bench_initial_resolution: Dictionary = observation_bench_bridge.resolve_interaction("obj_observation_bench", "sit")
	var observation_bench_default_interaction := observation_bench_bridge.default_interaction_type("obj_observation_bench")
	var archive_token_initial_resolution: Dictionary = archive_token_bridge.resolve_interaction("obj_archive_token", "grab")
	var archive_token_default_interaction := archive_token_bridge.default_interaction_type("obj_archive_token")
	var archive_token_initial_visible: bool = bool(archive_token.visible)
	var archive_storage_chest_initial_resolution: Dictionary = archive_storage_chest_bridge.resolve_interaction("obj_archive_storage_chest", "retrieve")
	var archive_storage_chest_default_interaction := archive_storage_chest_bridge.default_interaction_type("obj_archive_storage_chest")
	var stale_state: Dictionary = bridge.occupancy_sampler.object_states.get("obj_letter", {}).duplicate(true)
	stale_state["updated_at"] = 0
	bridge.occupancy_sampler.object_states["obj_letter"] = stale_state
	bridge.registry.occupancy_snapshot = bridge.occupancy_sampler.snapshot()
	bridge.registry.current_tick = bridge.registry.occupancy_freshness_ticks + 1
	var stale_refresh_resolution: Dictionary = bridge.resolve_interaction("obj_letter", "inspect")
	var initial_state := str(letter.get("current_state"))
	var plaque_initial_state := str(plaque.get("current_state"))
	var lamp_switch_initial_state := str(lamp_switch.get("current_state"))
	var archive_door_initial_state := str(archive_door.get("current_state"))
	var worktable_initial_state := str(worktable.get("current_state"))
	var observation_bench_initial_state := str(observation_bench.get("current_state"))
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus != null:
		bus.embodied_carry_place_event_received.emit({
			"event_type": "embodied.place.settled",
			"global_sequence": 1,
			"asset_ref": "item:archive_token_01",
			"actor_ref": "character:char_c",
			"drop_target_ref": "character:char_c:hand",
			"custody_holder_ref": "character:char_c:hand",
			"transaction_id": "tx:default-scene-pickup:1",
			"placement_directive": {
				"mode": "place_for_presentation",
				"asset_ref": "item:archive_token_01",
				"place_at_ref": "character:char_c:hand",
				"authority_only": false,
			},
		})
		bus.world_result_received.emit({
			"result_type": "object_state_result",
			"result_id": "object_result:obj_letter:101",
			"target_object_id": "obj_letter",
			"current_state": "visible",
			"settlement_status": "applied",
		})
		bus.world_result_received.emit({
			"result_type": "object_state_result",
			"result_id": "object_result:obj_observation_bench:113",
			"target_object_id": "obj_observation_bench",
			"machine_id": "seat_occupancy",
			"previous_state": "available",
			"current_state": "occupied",
			"settlement_status": "applied",
		})
		bus.world_result_received.emit({
			"result_type": "object_state_result",
			"result_id": "object_result:obj_worktable:110",
			"target_object_id": "obj_worktable",
			"machine_id": "work_surface",
			"previous_state": "ready",
			"current_state": "engaged",
			"settlement_status": "applied",
		})
		bus.world_result_received.emit({
			"result_type": "object_state_result",
			"result_id": "object_result:obj_archive_door:107",
			"target_object_id": "obj_archive_door",
			"machine_id": "door",
			"previous_state": "closed",
			"current_state": "open",
			"settlement_status": "applied",
		})
		bus.world_result_received.emit({
			"result_type": "object_state_result",
			"result_id": "object_result:obj_plaque:103",
			"target_object_id": "obj_plaque",
			"current_state": "visible",
			"settlement_status": "applied",
		})
		bus.world_result_received.emit({
			"result_type": "object_state_result",
			"result_id": "object_result:obj_lamp_switch:105",
			"target_object_id": "obj_lamp_switch",
			"machine_id": "switch",
			"previous_state": "idle",
			"current_state": "activated",
			"settlement_status": "applied",
		})
	await get_tree().process_frame
	var archive_token_visible_after_unsafe_directive: bool = bool(archive_token.visible)
	if bus != null:
		bus.embodied_carry_place_event_received.emit({
			"event_type": "embodied.place.settled",
			"global_sequence": 2,
			"asset_ref": "item:archive_token_01",
			"actor_ref": "character:char_c",
			"drop_target_ref": "character:char_c:hand",
			"custody_holder_ref": "character:char_c:hand",
			"transaction_id": "tx:default-scene-pickup:2",
			"placement_directive": {
				"mode": "place_for_presentation",
				"asset_ref": "item:archive_token_01",
				"place_at_ref": "character:char_c:hand",
				"authority_only": true,
			},
		})
	await get_tree().process_frame
	var archive_token_visible_after_authority: bool = bool(archive_token.visible)
	var archive_token_presentation_state := str(archive_token_presentation_bridge.presentation_state)
	var archive_token_stow_allowed_after_pickup := archive_token_presentation_bridge.can_request_stow("obj_archive_token")
	if bus != null:
		bus.embodied_inventory_stow_result_received.emit({
			"accepted": true,
			"target_object_id": "obj_archive_token",
			"transaction_id": "tx:default-scene-stow:unsafe",
			"presentation_directive": {
				"mode": "inventory_stowed_for_presentation",
				"authority_only": false,
			},
		})
	await get_tree().process_frame
	var archive_token_presentation_state_after_unsafe_stow := str(archive_token_presentation_bridge.presentation_state)
	if bus != null:
		bus.embodied_inventory_stow_result_received.emit({
			"accepted": true,
			"target_object_id": "obj_archive_token",
			"transaction_id": "tx:default-scene-stow:authority",
			"presentation_directive": {
				"mode": "inventory_stowed_for_presentation",
				"authority_only": true,
			},
		})
	await get_tree().process_frame
	var archive_token_presentation_state_after_authority_stow := str(archive_token_presentation_bridge.presentation_state)
	var archive_token_stow_allowed_after_authority_stow := archive_token_presentation_bridge.can_request_stow("obj_archive_token")
	if bus != null:
		bus.embodied_inventory_retrieve_result_received.emit({
			"accepted": true,
			"asset_ref": "item:archive_token_01",
			"transaction_id": "tx:default-scene-retrieve:unsafe",
			"presentation_directive": {
				"mode": "inventory_retrieved_for_presentation",
				"authority_only": false,
			},
		})
	await get_tree().process_frame
	var archive_token_presentation_state_after_unsafe_retrieve := str(archive_token_presentation_bridge.presentation_state)
	if bus != null:
		bus.embodied_inventory_retrieve_result_received.emit({
			"accepted": true,
			"asset_ref": "item:archive_token_01",
			"transaction_id": "tx:default-scene-retrieve:authority",
			"presentation_directive": {
				"mode": "inventory_retrieved_for_presentation",
				"authority_only": true,
			},
		})
	await get_tree().process_frame
	var archive_token_presentation_state_after_authority_retrieve := str(archive_token_presentation_bridge.presentation_state)
	var state_after_authority := str(letter.get("current_state"))
	var plaque_state_after_authority := str(plaque.get("current_state"))
	var lamp_switch_state_after_authority := str(lamp_switch.get("current_state"))
	var archive_door_state_after_authority := str(archive_door.get("current_state"))
	var worktable_state_after_authority := str(worktable.get("current_state"))
	var observation_bench_state_after_authority := str(observation_bench.get("current_state"))
	var archive_door_close_resolution: Dictionary = archive_door_bridge.resolve_interaction("obj_archive_door", "close")
	var archive_door_close_interaction := archive_door_bridge.default_interaction_type("obj_archive_door")
	var worktable_finish_resolution: Dictionary = worktable_bridge.resolve_interaction("obj_worktable", "finish_use")
	var worktable_finish_interaction := worktable_bridge.default_interaction_type("obj_worktable")
	var observation_bench_stand_resolution: Dictionary = observation_bench_bridge.resolve_interaction("obj_observation_bench", "stand")
	var observation_bench_stand_interaction := observation_bench_bridge.default_interaction_type("obj_observation_bench")
	if bus != null:
		bus.world_result_received.emit({
			"result_type": "object_state_result",
			"result_id": "object_result:obj_archive_door:109",
			"target_object_id": "obj_archive_door",
			"machine_id": "door",
			"previous_state": "open",
			"current_state": "closed",
			"settlement_status": "applied",
		})
		bus.world_result_received.emit({
			"result_type": "object_state_result",
			"result_id": "object_result:obj_observation_bench:115",
			"target_object_id": "obj_observation_bench",
			"machine_id": "seat_occupancy",
			"previous_state": "occupied",
			"current_state": "available",
			"settlement_status": "applied",
		})
		bus.world_result_received.emit({
			"result_type": "object_state_result",
			"result_id": "object_result:obj_worktable:112",
			"target_object_id": "obj_worktable",
			"machine_id": "work_surface",
			"previous_state": "engaged",
			"current_state": "ready",
			"settlement_status": "applied",
		})
	await get_tree().process_frame
	var archive_door_state_after_close := str(archive_door.get("current_state"))
	var archive_door_reopened_interaction := archive_door_bridge.default_interaction_type("obj_archive_door")
	var worktable_state_after_finish := str(worktable.get("current_state"))
	var worktable_reused_interaction := worktable_bridge.default_interaction_type("obj_worktable")
	var observation_bench_state_after_stand := str(observation_bench.get("current_state"))
	var observation_bench_resit_interaction := observation_bench_bridge.default_interaction_type("obj_observation_bench")
	if bus != null:
		bus.world_result_received.emit({
			"result_type": "constraint_state_result",
			"result_id": "constraint:obj_letter:102",
			"target_object_id": "obj_letter",
			"constraint_code": "out_of_range",
			"settlement_status": "rejected",
		})
		bus.world_result_received.emit({
			"result_type": "constraint_state_result",
			"result_id": "constraint:obj_observation_bench:114",
			"target_object_id": "obj_observation_bench",
			"constraint_code": "interaction_owner_mismatch",
			"settlement_status": "rejected",
		})
		bus.world_result_received.emit({
			"result_type": "constraint_state_result",
			"result_id": "constraint:obj_worktable:111",
			"target_object_id": "obj_worktable",
			"constraint_code": "invalid_interaction_state",
			"settlement_status": "rejected",
		})
		bus.world_result_received.emit({
			"result_type": "constraint_state_result",
			"result_id": "constraint:obj_archive_door:108",
			"target_object_id": "obj_archive_door",
			"constraint_code": "invalid_interaction_state",
			"settlement_status": "rejected",
		})
		bus.world_result_received.emit({
			"result_type": "constraint_state_result",
			"result_id": "constraint:obj_plaque:104",
			"target_object_id": "obj_plaque",
			"constraint_code": "out_of_range",
			"settlement_status": "rejected",
		})
		bus.world_result_received.emit({
			"result_type": "constraint_state_result",
			"result_id": "constraint:obj_lamp_switch:106",
			"target_object_id": "obj_lamp_switch",
			"constraint_code": "out_of_range",
			"settlement_status": "rejected",
		})
	await get_tree().process_frame
	var state_after_constraint := str(letter.get("current_state"))
	var plaque_state_after_constraint := str(plaque.get("current_state"))
	var lamp_switch_state_after_constraint := str(lamp_switch.get("current_state"))
	var archive_door_state_after_constraint := str(archive_door.get("current_state"))
	var worktable_state_after_constraint := str(worktable.get("current_state"))
	var observation_bench_state_after_constraint := str(observation_bench.get("current_state"))
	var resolved_after_authority: Dictionary = bridge.resolve_interaction("obj_letter", "read")
	var plaque_resolved_after_authority: Dictionary = plaque_bridge.resolve_interaction("obj_plaque", "inspect")
	var lamp_switch_resolved_after_authority: Dictionary = lamp_switch_bridge.resolve_interaction("obj_lamp_switch", "press")
	var archive_door_resolved_after_close: Dictionary = archive_door_bridge.resolve_interaction("obj_archive_door", "open")
	var worktable_resolved_after_finish: Dictionary = worktable_bridge.resolve_interaction("obj_worktable", "use")
	var observation_bench_resolved_after_stand: Dictionary = observation_bench_bridge.resolve_interaction("obj_observation_bench", "sit")
	var collider := letter.get_node_or_null("InteractionCollider/CollisionShape3D")
	var plaque_collider := plaque.get_node_or_null("InteractionCollider/CollisionShape3D")
	var lamp_switch_collider := lamp_switch.get_node_or_null("InteractionCollider/CollisionShape3D")
	var archive_door_collider := archive_door.get_node_or_null("InteractionCollider/CollisionShape3D")
	var worktable_collider := worktable.get_node_or_null("InteractionCollider/CollisionShape3D")
	var observation_bench_collider := observation_bench.get_node_or_null("InteractionCollider/CollisionShape3D")
	var ok: bool = (
		str(initial_resolution.get("status", "")) == "available"
		and str(letter_destroy_resolution.get("status", "")) == "available"
		and str(stale_refresh_resolution.get("status", "")) == "available"
		and initial_state == "partially_visible"
		and state_after_authority == "visible"
		and state_after_constraint == "visible"
		and str(resolved_after_authority.get("status", "")) == "available"
		and collider is CollisionShape3D
		and str(plaque_initial_resolution.get("status", "")) == "available"
		and plaque_initial_state == "partially_visible"
		and plaque_state_after_authority == "visible"
		and plaque_state_after_constraint == "visible"
		and str(plaque_resolved_after_authority.get("status", "")) == "available"
		and plaque_collider is CollisionShape3D
		and str(lamp_switch_initial_resolution.get("status", "")) == "available"
		and lamp_switch_default_interaction == "press"
		and lamp_switch_initial_state == "idle"
		and lamp_switch_state_after_authority == "activated"
		and lamp_switch_state_after_constraint == "activated"
		and str(lamp_switch_resolved_after_authority.get("status", "")) == "available"
		and lamp_switch_collider is CollisionShape3D
		and str(archive_door_initial_resolution.get("status", "")) == "available"
		and archive_door_default_interaction == "open"
		and archive_door_initial_state == "closed"
		and archive_door_state_after_authority == "open"
		and str(archive_door_close_resolution.get("status", "")) == "available"
		and archive_door_close_interaction == "close"
		and archive_door_state_after_close == "closed"
		and archive_door_reopened_interaction == "open"
		and archive_door_state_after_constraint == "closed"
		and str(archive_door_resolved_after_close.get("status", "")) == "available"
		and archive_door_collider is CollisionShape3D
		and str(worktable_initial_resolution.get("status", "")) == "available"
		and worktable_default_interaction == "use"
		and worktable_initial_state == "ready"
		and worktable_state_after_authority == "engaged"
		and str(worktable_finish_resolution.get("status", "")) == "available"
		and worktable_finish_interaction == "finish_use"
		and worktable_state_after_finish == "ready"
		and worktable_reused_interaction == "use"
		and worktable_state_after_constraint == "ready"
		and str(worktable_resolved_after_finish.get("status", "")) == "available"
		and worktable_collider is CollisionShape3D
		and str(observation_bench_initial_resolution.get("status", "")) == "available"
		and observation_bench_default_interaction == "sit"
		and observation_bench_initial_state == "available"
		and observation_bench_state_after_authority == "occupied"
		and str(observation_bench_stand_resolution.get("status", "")) == "available"
		and observation_bench_stand_interaction == "stand"
		and observation_bench_state_after_stand == "available"
		and observation_bench_resit_interaction == "sit"
		and observation_bench_state_after_constraint == "available"
		and str(observation_bench_resolved_after_stand.get("status", "")) == "available"
		and observation_bench_collider is CollisionShape3D
		and str(archive_token_initial_resolution.get("status", "")) == "available"
		and archive_token_default_interaction == "grab"
		and archive_token_initial_visible
		and archive_token_visible_after_unsafe_directive
		and not archive_token_visible_after_authority
		and archive_token_presentation_state == "carried"
		and archive_token_stow_allowed_after_pickup
		and archive_token_presentation_state_after_unsafe_stow == "carried"
		and archive_token_presentation_state_after_authority_stow == "stowed"
		and not archive_token_stow_allowed_after_authority_stow
		and str(archive_storage_chest_initial_resolution.get("status", "")) == "available"
		and archive_storage_chest_default_interaction == "retrieve"
		and archive_token_presentation_state_after_unsafe_retrieve == "stowed"
		and archive_token_presentation_state_after_authority_retrieve == "carried"
	)
	var report := {
		"status": "godot-runtime-default-scene-letter-affordance-verified" if ok else "godot-runtime-default-scene-letter-affordance-failed",
		"initial_resolution": initial_resolution,
		"letter_destroy_resolution": letter_destroy_resolution,
		"stale_refresh_resolution": stale_refresh_resolution,
		"initial_state": initial_state,
		"state_after_authority": state_after_authority,
		"state_after_constraint": state_after_constraint,
		"resolved_after_authority": resolved_after_authority,
		"collider_class": collider.get_class() if collider != null else "",
		"authority_owned_presentation": state_after_authority == "visible" and state_after_constraint == "visible",
		"plaque_initial_resolution": plaque_initial_resolution,
		"plaque_initial_state": plaque_initial_state,
		"plaque_state_after_authority": plaque_state_after_authority,
		"plaque_state_after_constraint": plaque_state_after_constraint,
		"plaque_resolved_after_authority": plaque_resolved_after_authority,
		"plaque_collider_class": plaque_collider.get_class() if plaque_collider != null else "",
		"plaque_authority_owned_presentation": plaque_state_after_authority == "visible" and plaque_state_after_constraint == "visible",
		"lamp_switch_initial_resolution": lamp_switch_initial_resolution,
		"lamp_switch_default_interaction": lamp_switch_default_interaction,
		"lamp_switch_initial_state": lamp_switch_initial_state,
		"lamp_switch_state_after_authority": lamp_switch_state_after_authority,
		"lamp_switch_state_after_constraint": lamp_switch_state_after_constraint,
		"lamp_switch_resolved_after_authority": lamp_switch_resolved_after_authority,
		"lamp_switch_collider_class": lamp_switch_collider.get_class() if lamp_switch_collider != null else "",
		"lamp_switch_authority_owned_presentation": lamp_switch_state_after_authority == "activated" and lamp_switch_state_after_constraint == "activated",
		"archive_door_initial_resolution": archive_door_initial_resolution,
		"archive_door_default_interaction": archive_door_default_interaction,
		"archive_door_initial_state": archive_door_initial_state,
		"archive_door_state_after_authority": archive_door_state_after_authority,
		"archive_door_close_resolution": archive_door_close_resolution,
		"archive_door_close_interaction": archive_door_close_interaction,
		"archive_door_state_after_close": archive_door_state_after_close,
		"archive_door_reopened_interaction": archive_door_reopened_interaction,
		"archive_door_state_after_constraint": archive_door_state_after_constraint,
		"archive_door_resolved_after_close": archive_door_resolved_after_close,
		"archive_door_collider_class": archive_door_collider.get_class() if archive_door_collider != null else "",
		"archive_door_authority_owned_presentation": archive_door_state_after_authority == "open" and archive_door_state_after_close == "closed" and archive_door_state_after_constraint == "closed",
		"worktable_initial_resolution": worktable_initial_resolution,
		"worktable_default_interaction": worktable_default_interaction,
		"worktable_initial_state": worktable_initial_state,
		"worktable_state_after_authority": worktable_state_after_authority,
		"worktable_finish_resolution": worktable_finish_resolution,
		"worktable_finish_interaction": worktable_finish_interaction,
		"worktable_state_after_finish": worktable_state_after_finish,
		"worktable_reused_interaction": worktable_reused_interaction,
		"worktable_state_after_constraint": worktable_state_after_constraint,
		"worktable_resolved_after_finish": worktable_resolved_after_finish,
		"worktable_collider_class": worktable_collider.get_class() if worktable_collider != null else "",
		"worktable_authority_owned_presentation": worktable_state_after_authority == "engaged" and worktable_state_after_finish == "ready" and worktable_state_after_constraint == "ready",
		"observation_bench_initial_resolution": observation_bench_initial_resolution,
		"observation_bench_default_interaction": observation_bench_default_interaction,
		"observation_bench_initial_state": observation_bench_initial_state,
		"observation_bench_state_after_authority": observation_bench_state_after_authority,
		"observation_bench_stand_resolution": observation_bench_stand_resolution,
		"observation_bench_stand_interaction": observation_bench_stand_interaction,
		"observation_bench_state_after_stand": observation_bench_state_after_stand,
		"observation_bench_resit_interaction": observation_bench_resit_interaction,
		"observation_bench_state_after_constraint": observation_bench_state_after_constraint,
		"observation_bench_resolved_after_stand": observation_bench_resolved_after_stand,
		"observation_bench_collider_class": observation_bench_collider.get_class() if observation_bench_collider != null else "",
		"observation_bench_authority_owned_presentation": observation_bench_state_after_authority == "occupied" and observation_bench_state_after_stand == "available" and observation_bench_state_after_constraint == "available",
		"archive_token_initial_resolution": archive_token_initial_resolution,
		"archive_token_default_interaction": archive_token_default_interaction,
		"archive_token_initial_visible": archive_token_initial_visible,
		"archive_token_visible_after_unsafe_directive": archive_token_visible_after_unsafe_directive,
		"archive_token_visible_after_authority": archive_token_visible_after_authority,
		"archive_token_presentation_state": archive_token_presentation_state,
		"archive_token_stow_allowed_after_pickup": archive_token_stow_allowed_after_pickup,
		"archive_token_presentation_state_after_unsafe_stow": archive_token_presentation_state_after_unsafe_stow,
		"archive_token_presentation_state_after_authority_stow": archive_token_presentation_state_after_authority_stow,
		"archive_token_stow_allowed_after_authority_stow": archive_token_stow_allowed_after_authority_stow,
		"archive_token_authority_owned_presentation": archive_token_visible_after_unsafe_directive and not archive_token_visible_after_authority,
		"archive_storage_chest_initial_resolution": archive_storage_chest_initial_resolution,
		"archive_storage_chest_default_interaction": archive_storage_chest_default_interaction,
		"archive_token_presentation_state_after_unsafe_retrieve": archive_token_presentation_state_after_unsafe_retrieve,
		"archive_token_presentation_state_after_authority_retrieve": archive_token_presentation_state_after_authority_retrieve,
	}
	var report_path := _write_json(".harness/verification/default-scene-letter-affordance-godot-runtime.json", report)
	print("default_scene_letter_affordance_probe:artifact=%s" % report_path)
	print("default_scene_letter_affordance_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
