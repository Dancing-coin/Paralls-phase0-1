from app.models.player_input import InteractIntent
from app.services.esm_service import ESMService


def test_esm_service_builds_action_request_from_interact_intent() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=9,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )

    request = service.build_action_request(event, source_system="player_input_bridge")

    assert request.request_type == "interact"
    assert request.room_id == "room_demo"
    assert request.scene_id == "scene_demo"
    assert request.zone_id == "zone_focus"
    assert request.source["layer"] == "L1"
    assert request.source["system"] == "player_input_bridge"
    assert request.source["actor_id"] == "char_c"
    assert request.target_entity_refs["object_ids"] == ["obj_letter"]
    assert request.action_profile == "inspect"
    assert request.causation_id == "interact:9"
    assert request.correlation_id == "interact:9"


def test_esm_service_accepts_nearby_interaction() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=10,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = service.resolve_interaction(event, is_in_range=True)
    assert result.result_type == "object_interaction_result"


def test_esm_service_rejects_out_of_range_interaction() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=11,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = service.resolve_interaction(event, is_in_range=False)
    assert result.result_type == "constraint_state_result"
    assert result.constraint_type == "distance"


def test_esm_service_computes_range_from_actor_position() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=12,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    near = service.resolve_interaction(event, actor_position=(0.0, 1.0, -0.5))
    far = service.resolve_interaction(event, actor_position=(0.0, 1.0, 20.0))

    assert near.result_type == "object_interaction_result"
    assert far.result_type == "constraint_state_result"


def test_esm_service_rejects_far_actor_position() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=12,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = service.resolve_interaction(event, actor_position=(0.0, 0.0, 16.0))
    assert result.result_type == "constraint_state_result"
    assert result.constraint_type == "distance"


def test_esm_service_success_result_exposes_stable_phase1_contract_fields() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=20,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )

    result = service.resolve_interaction(event, is_in_range=True)

    assert result.result_type == "object_interaction_result"
    assert result.actor_id == "char_c"
    assert result.scene_id == "scene_demo"
    assert result.zone_id == "zone_focus"
    assert result.request_ref == "interact:20:obj_letter"
    assert result.result_id == "resolution:interact:20:obj_letter"
    assert result.causation_id == "interact:20"
    assert result.correlation_id == "interact:20"
    assert result.settlement_status == "accepted"
    assert result.resolved_entities == ["obj_letter"]
    assert result.applied_state_changes == ["object_interaction_result"]
    assert result.stable_state_summary == "object_interaction accepted"


def test_esm_service_constraint_result_exposes_stable_phase1_contract_fields() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=21,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )

    result = service.resolve_interaction(event, is_in_range=False)

    assert result.result_type == "constraint_state_result"
    assert result.actor_id == "char_c"
    assert result.scene_id == "scene_demo"
    assert result.zone_id == "zone_focus"
    assert result.request_ref == "interact:21:obj_letter"
    assert result.result_id == "constraint:interact:21:obj_letter"
    assert result.causation_id == "interact:21"
    assert result.correlation_id == "interact:21"
    assert result.constraint_type == "distance"
    assert result.constraint_code == "distance_constraint"
    assert result.blocking_entity_refs == ["obj_letter"]
    assert result.settlement_status == "rejected"


def test_esm_service_environment_shift_result_is_replayable_and_updates_field_state() -> None:
    service = ESMService()

    result = service.emit_environment_shift(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        target_environment_id="env_lamp",
        previous_state="stable",
        current_state="alerted",
    )

    assert result.result_type == "environment_state_result"
    assert result.actor_id == "char_c"
    assert result.scene_id == "scene_demo"
    assert result.zone_id == "zone_focus"
    assert result.causation_id == "env:env_lamp:alerted"
    assert result.correlation_id == "env:env_lamp:alerted"
    assert result.settlement_status == "applied"
    assert result.affected_zone_ids == ["zone_focus"]
    assert result.field_delta_summary == ["light_level", "noise_level", "smoke_density", "visibility_level"]
    assert result.light_level == "low"
    assert result.noise_level == "elevated"
    assert result.smoke_density == "light"
    assert result.visibility_level == "reduced"

    field = service.get_environment_field("room_demo", "zone_focus")
    assert field.scene_id == "scene_demo"
    assert field.light_level == "low"
    assert field.noise_level == "elevated"
    assert field.temperature == "ambient"
    assert field.humidity == "stable"
    assert field.smoke_density == "light"
    assert field.visibility_level == "reduced"


def test_esm_service_object_state_result_is_replayable() -> None:
    service = ESMService()

    result = service.emit_object_state_result(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        target_object_id="obj_letter",
        previous_state="idle",
        current_state="inspected",
        producer_ts=220,
    )

    assert result.result_type == "object_state_result"
    assert result.request_ref == "object:obj_letter:220"
    assert result.result_id == "object_result:obj_letter:220"
    assert result.target_object_id == "obj_letter"
    assert result.previous_state == "idle"
    assert result.current_state == "inspected"
    assert result.change_summary == "obj_letter changed from idle to inspected"


def test_esm_service_action_resolution_result_is_replayable() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=230,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    interaction_result = service.resolve_interaction(event, is_in_range=True)

    result = service.emit_action_resolution_result(event, interaction_result)

    assert result.result_type == "action_resolution_result"
    assert result.request_ref == "interact:230:obj_letter"
    assert result.result_id == "action_resolution:interact:230:obj_letter"
    assert result.target_object_id == "obj_letter"
    assert result.resolution_status == "accepted"
    assert result.resolved_entities == ["obj_letter"]
    assert result.applied_state_changes == ["object_interaction_result"]
    assert result.stable_state_summary == "object_interaction accepted"


def test_esm_service_propagates_noise_and_smoke_to_adjacent_zone() -> None:
    service = ESMService()

    service.emit_environment_shift(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        target_environment_id="env_lamp",
        previous_state="stable",
        current_state="alerted",
        producer_ts=300,
    )
    propagated = service.propagate_environment_field_to_adjacent_zones(
        room_id="room_demo",
        scene_id="scene_demo",
        source_zone_id="zone_focus",
        adjacent_zone_ids=["zone_adjacent"],
        producer_ts=301,
    )

    assert propagated["zone_adjacent"].noise_level == "moderate"
    assert propagated["zone_adjacent"].smoke_density == "trace"
    assert propagated["zone_adjacent"].visibility_level == "soft_reduced"


def test_esm_service_exposes_state_machine_and_material_templates() -> None:
    service = ESMService()

    burning_machine = service.get_state_machine_template("burning")
    lock_machine = service.get_state_machine_template("lock")
    wood_material = service.get_material_template("wood")
    fabric_material = service.get_material_template("fabric")

    assert burning_machine["machine_id"] == "burning"
    assert "burning" in burning_machine["state_list"]
    assert lock_machine["machine_id"] == "lock"
    assert "locked" in lock_machine["state_list"]
    assert wood_material["material_id"] == "wood"
    assert wood_material["flammability"] == "medium"
    assert fabric_material["material_id"] == "fabric"
    assert fabric_material["smoke_factor"] == "high"
